"""Usage statistics from the MCP server's `--log` file: recalls by mode, estimated savings, worst trails."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ragtrail.models import Mode
from ragtrail.store import TrajectoryStore, utc_now

DEFAULT_TOKENS_PER_CALL = 500
WORST_LIMIT = 5


@dataclass(frozen=True)
class TrailUsage:
    """How often one trail was recalled and how often its answer was rejected in the window."""

    trajectory_id: str
    query: str
    recalls: int
    rejections: int


@dataclass(frozen=True)
class Stats:
    """Result of `compute_stats`; `tokens_saved` is an estimate (`calls_saved` times `tokens_per_call`)."""

    days: float
    modes: dict[Mode, int]
    calls_saved: int
    tokens_saved: int
    tokens_per_call: int
    worst: list[TrailUsage] = field(default_factory=list)

    @property
    def recalls(self) -> int:
        return sum(self.modes.values())


def read_log(path: Path) -> list[dict[str, Any]]:
    """Parse a `--log` file, skipping lines that are not JSON objects."""
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _within(entry: dict[str, Any], scope: str, since: datetime) -> bool:
    if entry.get("scope", scope) != scope or entry.get("error"):
        return False
    try:
        return datetime.fromisoformat(entry["ts"]) >= since
    except (KeyError, ValueError, TypeError):
        return False


def compute_stats(
    entries: Iterable[dict[str, Any]],
    store: TrajectoryStore,
    scope: str,
    *,
    days: float,
    tokens_per_call: int = DEFAULT_TOKENS_PER_CALL,
    now: datetime | None = None,
) -> Stats:
    """Aggregate the log entries of `scope` from the last `days` days.

    Estimated savings: each `hint` or `prefetch` recall of a trail with `n` recorded steps counts `n - 1`
    search calls skipped (the agent still makes one read); tokens are that times `tokens_per_call`, an
    assumption to calibrate against your own traces. Worst trails: most rejections, then rejection rate.
    Entries without a timestamp (logs from older versions) are ignored.

    >>> from ragtrail.store import SQLiteStore
    >>> compute_stats([], SQLiteStore(":memory:"), "acme", days=7).recalls
    0
    """
    since = (now or utc_now()) - timedelta(days=days)
    modes: Counter[Mode] = Counter()
    recalled: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    for entry in entries:
        if not _within(entry, scope, since):
            continue
        if entry.get("tool") == "recall" and entry.get("mode") in ("prefetch", "hint", "miss"):
            modes[entry["mode"]] += 1
            if entry.get("trajectory_id"):
                recalled[entry["trajectory_id"]] += 1
        elif entry.get("tool") == "reject":
            rejected.update(entry.get("rejected") or [])
    calls_saved = 0
    usage = []
    for trajectory_id in recalled.keys() | rejected.keys():
        trajectory = store.get(scope, trajectory_id)
        if trajectory is None:
            continue
        calls_saved += recalled[trajectory_id] * max(0, len(trajectory.steps) - 1)
        usage.append(
            TrailUsage(trajectory_id, trajectory.query, recalled[trajectory_id], rejected[trajectory_id])
        )
    worst = sorted(
        (u for u in usage if u.rejections),
        key=lambda u: (-u.rejections, -u.rejections / max(u.recalls, 1), u.trajectory_id),
    )[:WORST_LIMIT]
    return Stats(
        days=days,
        modes={m: modes[m] for m in ("prefetch", "hint", "miss")},
        calls_saved=calls_saved,
        tokens_saved=calls_saved * tokens_per_call,
        tokens_per_call=tokens_per_call,
        worst=worst,
    )


def format_stats(stats: Stats, scope: str) -> str:
    """Plain-text report for the terminal."""
    total = stats.recalls
    lines = [f"ragtrail stats — scope {scope}, last {stats.days:g} days", "", f"Recalls: {total}"]
    for mode, count in stats.modes.items():
        share = f" ({count / total:.0%})" if total else ""
        lines.append(f"  {mode:<9}{count:>6}{share}")
    lines += [
        "",
        f"Search calls skipped (est.): {stats.calls_saved}",
        f"Tokens saved (est.): {stats.tokens_saved} at {stats.tokens_per_call} tokens per call (assumed)",
        "",
        "Worst trails (rejected answers):",
    ]
    if not stats.worst:
        lines.append("  none")
    else:
        lines.append(f"  {'rejected':>8} {'recalled':>8}  trail   question")
        for u in stats.worst:
            query = u.query if len(u.query) <= 60 else u.query[:57] + "..."
            lines.append(f"  {u.rejections:>8} {u.recalls:>8}  {u.trajectory_id[:8]}  {query}")
    return "\n".join(lines)
