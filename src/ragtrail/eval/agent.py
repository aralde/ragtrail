"""Agent runs through `claude -p`: `cold` (empty trail store) vs `warm` (pre-warmed), same everything else.

Each run starts a fresh `claude -p` whose only tools are subforest's docs server (chunks view) and a
recall-only ragtrail server. Both arms see the same tools and system prompt; in `cold` every recall misses.
Each warm run gets its own copy of the warm store, so runs never feed each other.
Results go to `runs-<scenario>.jsonl`, so an interrupted run resumes where it stopped.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ragtrail.eval.claude import Invoke, UsageLimitReached, parse_output, run_claude
from ragtrail.eval.data import EvalQuestion
from ragtrail.eval.offline import RecallRow

Arm = Literal["cold", "warm"]
ARMS: tuple[Arm, ...] = ("cold", "warm")
SCOPE = "eval"

SYSTEM_PROMPT = """\
You answer questions about {corpus} using only the tools you are given.
Start by calling `recall` with the user's question copied verbatim (not rephrased, not keywords):
- mode=prefetch: it includes the text of documentation that answered a similar question. If that text answers
  this question, answer from it without searching; otherwise use the docs tools.
- mode=hint: read the listed node ids first; search only if they do not cover the question.
- mode=miss: use `search` and `read`.
Use at most {max_calls} tool calls in total. Base the answer on what you read, and say so if the docs do not
cover it. Give a concise answer in plain text."""

RECORD_STEP = """
After you have the answer, and only if it is grounded in the docs you read, call `record` once with the user's
question verbatim, `cited` = the node ids (like "n123") your answer relies on, and outcome "accepted".
Then give the answer."""

_NODE = re.compile(r"\[n(\d+)\]")


@dataclass
class AgentConfig:
    """Settings shared by both arms."""

    model: str = "haiku"
    max_calls: int = 10
    docs_budget: int = 800
    recall_budget: int = 2000
    embed: str | None = None
    allow_record: bool = False
    corpus_name: str = "the Wix help center"
    claude: str = "claude"
    python: str = sys.executable
    strip_context: str | None = None


def mcp_config(
    config: AgentConfig, corpus: Path, trails: Path, work: Path, scope: str = SCOPE
) -> dict[str, Any]:
    """Two stdio servers: `docs` (subforest, chunks view) and `trails` (ragtrail, recall only), both logging.

    >>> cfg = mcp_config(AgentConfig(python="py"), Path("c.db"), Path("t.db"), Path("w"))
    >>> sorted(cfg["mcpServers"]), "--no-record" in cfg["mcpServers"]["trails"]["args"]
    (['docs', 'trails'], True)
    """
    docs = ["-m", "subforest.cli", "serve", "--db", str(corpus), "--view", "chunks"]
    docs += ["--budget", str(config.docs_budget), "--max-calls", str(config.max_calls)]
    docs += ["--log", str(work / "docs.jsonl")]
    trail = ["-m", "ragtrail.cli", "serve", "--db", str(trails), "--scope", scope, "--subforest", str(corpus)]
    trail += ["--budget", str(config.recall_budget), "--log", str(work / "trails.jsonl")]
    if not config.allow_record:
        trail.append("--no-record")
    if config.embed:
        trail += ["--embed", config.embed]
    if config.strip_context:
        trail += ["--strip-context", config.strip_context]
    return {
        "mcpServers": {
            "docs": {"command": config.python, "args": docs},
            "trails": {"command": config.python, "args": trail},
        }
    }


def claude_command(config: AgentConfig, mcp_path: Path, question: str) -> list[str]:
    """The `claude -p` command for one run: no built-in tools, only the two MCP servers.

    >>> cmd = claude_command(AgentConfig(), Path("m.json"), "How?")
    >>> cmd[:3], cmd[cmd.index("--allowedTools") + 1]
    (['claude', '-p', 'How?'], 'mcp__docs,mcp__trails')
    """
    return [
        config.claude,
        "-p",
        question,
        "--model",
        config.model,
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        str(mcp_path),
        "--allowedTools",
        "mcp__docs,mcp__trails",
        "--system-prompt",
        SYSTEM_PROMPT.format(corpus=config.corpus_name, max_calls=config.max_calls)
        + (RECORD_STEP if config.allow_record else ""),
        "--output-format",
        "json",
        "--no-session-persistence",
    ]


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_one(
    question: EvalQuestion,
    arm: Arm,
    scenario: str,
    corpus: Path,
    warm_db: Path,
    config: AgentConfig,
    invoke: Invoke = run_claude,
    scope: str = SCOPE,
) -> dict[str, Any]:
    """Run one question in one arm and return the record written to `runs-<scenario>.jsonl`."""
    with tempfile.TemporaryDirectory(prefix="ragtrail-run-") as tmp:
        work = Path(tmp)
        trails = work / "trails.db"
        if arm == "warm":
            shutil.copyfile(warm_db, trails)
        mcp_path = work / "mcp.json"
        mcp_path.write_text(json.dumps(mcp_config(config, corpus, trails, work, scope)), encoding="utf-8")
        start = time.monotonic()
        stdout = invoke(claude_command(config, mcp_path, question.question), work)
        elapsed = time.monotonic() - start
        docs_log, trails_log = _jsonl(work / "docs.jsonl"), _jsonl(work / "trails.jsonl")
    out = parse_output(stdout)
    usage = out.get("usage") or {}
    return {
        "id": question.id,
        "scenario": scenario,
        "arm": arm,
        "model": config.model,
        "status": "error" if out.get("is_error") else "ok",
        "answer": str(out.get("result") or ""),
        "seconds": round(elapsed, 2),
        "turns": out.get("num_turns"),
        "input_tokens": sum(
            usage.get(k, 0)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        ),
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd_equivalent": out.get("total_cost_usd"),
        "docs_calls": [
            {
                "tool": c["tool"],
                "args": c["args"],
                "shown": sorted({f"n{m}" for m in _NODE.findall(c.get("text", ""))}),
                "error": c.get("error", False),
                "blocked": c.get("blocked", False),
            }
            for c in docs_log
        ],
        "trail_calls": [
            {
                "query": c.get("args", {}).get("query"),
                "mode": c.get("mode"),
                "nodes": c.get("nodes", []),
                "similarity": c.get("similarity"),
            }
            for c in trails_log
            if c.get("tool", "recall") == "recall"
        ],
        "records": [
            {**c.get("args", {}), "recorded": c.get("recorded", False), "nodes": c.get("nodes", [])}
            for c in trails_log
            if c.get("tool") == "record"
        ],
    }


def select_pilot(rows: Sequence[RecallRow], n: int, *, seed: int = 0, matched_first: bool) -> list[str]:
    """Question ids for an agent pilot, in a stable order.

    `matched_first=True` takes every question whose warm recall was not a miss, then fills with seeded
    random misses (for sparse scenarios); otherwise a seeded random sample of all questions.

    >>> rows = [RecallRow(str(i), "miss" if i % 3 else "hint", 0.0, (), False, 0) for i in range(9)]
    >>> select_pilot(rows, 4, matched_first=True)[:3]
    ['0', '3', '6']
    """
    rng = random.Random(seed)
    if not matched_first:
        return [r.id for r in rng.sample(list(rows), min(n, len(rows)))]
    matched = [r.id for r in rows if r.mode != "miss"][:n]
    misses = [r.id for r in rows if r.mode == "miss"]
    return matched + rng.sample(misses, min(len(misses), n - len(matched)))


def load_runs(path: Path) -> list[dict[str, Any]]:
    """Read a runs file; a later line for the same question and arm replaces an earlier one."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for record in _jsonl(path):
        latest[(record["id"], record["arm"])] = record
    return list(latest.values())


def pending(
    questions: Sequence[EvalQuestion], done: Iterable[dict[str, Any]], arms: Sequence[Arm] = ARMS
) -> list[tuple[EvalQuestion, Arm]]:
    """(question, arm) pairs without an `ok` record, arms interleaved so a partial run stays paired.

    >>> qs = [EvalQuestion(id=i, split="s", question="?", answer="") for i in "ab"]
    >>> [(q.id, a) for q, a in pending(qs, [{"id": "a", "arm": "cold", "status": "ok"}])]
    [('a', 'warm'), ('b', 'cold'), ('b', 'warm')]
    """
    finished = {(r["id"], r["arm"]) for r in done if r["status"] == "ok"}
    return [(q, a) for q in questions for a in arms if (q.id, a) not in finished]


def run_agent(
    questions: Sequence[EvalQuestion],
    runs_path: Path,
    *,
    scenario: str,
    corpus: Path,
    warm_db: Path,
    config: AgentConfig,
    max_runs: int | None = None,
    arms: Sequence[Arm] = ARMS,
    invoke: Invoke = run_claude,
    echo: Callable[[str], None] = print,
    scope_of: Callable[[EvalQuestion], str] | None = None,
) -> int:
    """Run pending pairs, appending to `runs_path`; stops early (no error) at the usage limit.

    `scope_of` gives each question its own trail scope (for example its paper); default: one shared scope."""
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    todo = pending(questions, load_runs(runs_path), arms)[:max_runs]
    for i, (question, arm) in enumerate(todo, 1):
        try:
            scope = scope_of(question) if scope_of is not None else SCOPE
            record = run_one(question, arm, scenario, corpus, warm_db, config, invoke, scope)
        except UsageLimitReached as exc:
            echo(f"usage limit reached after {i - 1} runs; rerun later to resume ({exc})")
            return i - 1
        with runs_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        modes = ",".join(str(c["mode"]) for c in record["trail_calls"]) or "-"
        calls = len(record["docs_calls"]) + len(record["trail_calls"])
        echo(f"[{i}/{len(todo)}] {question.id} {arm}: {record['status']}, {calls} calls, recall={modes}")
    return len(todo)
