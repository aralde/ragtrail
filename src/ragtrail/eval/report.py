"""Score agent runs (paired cold vs warm) and render the Markdown report."""

from __future__ import annotations

import hashlib
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ragtrail.eval.agent import ARMS, Arm
from ragtrail.eval.data import EvalQuestion
from ragtrail.eval.judge import SCORES
from ragtrail.eval.stats import bootstrap_ci, sign_test, token_f1

DocOf = Callable[[str], str | None]


def judge_key(scenario: str, question_id: str, arm: str) -> str:
    """Opaque key for a judged answer, so the judge cannot tell the arms apart.

    >>> len(judge_key("repeat", "q1", "warm")), judge_key("s", "q", "cold") != judge_key("s", "q", "warm")
    (12, True)
    """
    return hashlib.sha1(f"{scenario}|{question_id}|{arm}".encode()).hexdigest()[:12]


@dataclass
class RunScore:
    """Per-run metrics."""

    calls: int
    docs_calls: int
    input_tokens: int
    seconds: float
    gold_seen: bool
    f1: float
    judge: float | None
    recall_mode: str


def score_run(run: dict[str, Any], question: EvalQuestion, doc_of: DocOf, judge: float | None) -> RunScore:
    """Score one run: a gold doc counts as seen if a read node, a search-shown chunk node (chunks view shows
    text) or a prefetched node belongs to a gold document.

    >>> run = {"docs_calls": [{"tool": "read", "args": {"node_id": "n9"}, "shown": ["n9"], "error": False,
    ...        "blocked": False}], "trail_calls": [{"mode": "miss", "nodes": []}], "input_tokens": 10,
    ...        "seconds": 1.0, "answer": "Open settings"}
    >>> q = EvalQuestion(id="q", split="s", question="?", answer="Open settings", gold=["n7"])
    >>> s = score_run(run, q, {"n9": "n7"}.get, None)
    >>> s.calls, s.gold_seen, s.recall_mode
    (2, True, 'miss')
    """
    gold = set(q for q in question.gold)
    seen: set[str] = set()
    for call in run["docs_calls"]:
        if call["error"] or call["blocked"]:
            continue
        ids = list(call["shown"])
        if call["tool"] == "read":
            ids.append(str(call["args"].get("node_id", "")))
        seen |= {d for i in ids if (d := doc_of(i if i.startswith("n") else f"n{i}")) is not None}
    for call in run["trail_calls"]:
        if call["mode"] == "prefetch":
            seen |= {d for i in call["nodes"] if (d := doc_of(i)) is not None}
    first = run["trail_calls"][0]["mode"] if run["trail_calls"] else "none"
    return RunScore(
        calls=len(run["docs_calls"]) + len(run["trail_calls"]),
        docs_calls=len(run["docs_calls"]),
        input_tokens=int(run["input_tokens"]),
        seconds=float(run["seconds"]),
        gold_seen=bool(seen & gold),
        f1=token_f1(run["answer"], question.answer),
        judge=judge,
        recall_mode=str(first),
    )


@dataclass
class Paired:
    """Scores of questions finished in both arms, in the same order."""

    ids: list[str] = field(default_factory=list)
    arms: dict[Arm, list[RunScore]] = field(default_factory=lambda: {a: [] for a in ARMS})


def pair_runs(
    scenario: str,
    runs: Sequence[dict[str, Any]],
    questions: Sequence[EvalQuestion],
    doc_of: DocOf,
    verdicts: dict[str, str],
) -> Paired:
    """Keep questions with an `ok` run in both arms and score them."""
    ok = {(r["id"], r["arm"]): r for r in runs if r["status"] == "ok"}
    paired = Paired()
    for q in questions:
        if not all((q.id, a) in ok for a in ARMS):
            continue
        paired.ids.append(q.id)
        for arm in ARMS:
            verdict = verdicts.get(judge_key(scenario, q.id, arm))
            score = SCORES[verdict] if verdict is not None else None
            paired.arms[arm].append(score_run(ok[(q.id, arm)], q, doc_of, score))
    return paired


def _mean(xs: Sequence[float]) -> float:
    return statistics.fmean(xs) if xs else 0.0


def agent_markdown(paired: Paired, model: str) -> str:
    """Paired cold vs warm table, deltas with 95% bootstrap CIs, and a breakdown by warm recall mode."""
    cold, warm = paired.arms["cold"], paired.arms["warm"]
    n = len(paired.ids)
    if n == 0:
        return "No question finished in both arms yet.\n"
    judged = [i for i in range(n) if cold[i].judge is not None and warm[i].judge is not None]

    def metric(name: str, get: Callable[[RunScore], float], fmt: str, idx: Sequence[int]) -> str:
        xs, ys = [get(cold[i]) for i in idx], [get(warm[i]) for i in idx]
        diffs = [y - x for x, y in zip(xs, ys, strict=True)]
        lo, hi = bootstrap_ci(diffs)
        return (
            f"| {name} | {_mean(xs):{fmt}} | {_mean(ys):{fmt}} | {_mean(diffs):+{fmt}} "
            f"| {lo:+{fmt}} to {hi:+{fmt}} |"
        )

    every = range(n)
    lines = [
        f"{n} questions answered in both arms by `{model}` through `claude -p`; "
        "same tools, prompt and call cap.",
        "",
        "| Metric | cold | warm | Δ warm - cold | 95% CI |",
        "|---|---|---|---|---|",
        metric("Tool calls (incl. recall)", lambda s: s.calls, ".2f", every),
        metric("Docs tool calls", lambda s: s.docs_calls, ".2f", every),
        metric("Input tokens", lambda s: s.input_tokens, ",.0f", every),
        metric("Seconds", lambda s: s.seconds, ".1f", every),
        metric("Saw a gold doc", lambda s: float(s.gold_seen), ".1%", every),
        metric("Answer token F1", lambda s: s.f1, ".3f", every),
    ]
    if judged:
        lines.append(metric(f"Judge accuracy (n={len(judged)})", lambda s: s.judge or 0.0, ".1%", judged))
        wins = sum((warm[i].judge or 0) > (cold[i].judge or 0) for i in judged)
        losses = sum((warm[i].judge or 0) < (cold[i].judge or 0) for i in judged)
        lines += [
            "",
            f"Judge: warm better on {wins}, cold better on {losses}; sign test p = "
            f"{sign_test(wins, losses):.3f}.",
        ]
    lines += [
        "",
        "By warm recall mode:",
        "",
        "| Warm recall | Questions | Calls cold → warm | Input tokens cold → warm | Judge cold → warm |",
        "|---|---|---|---|---|",
    ]
    for mode in ("prefetch", "hint", "miss"):
        idx = [i for i in every if warm[i].recall_mode == mode]
        if not idx:
            continue
        jdx = [i for i in idx if i in judged]
        judge = (
            f"{_mean([cold[i].judge or 0 for i in jdx]):.0%} → {_mean([warm[i].judge or 0 for i in jdx]):.0%}"
            if jdx
            else "—"
        )
        lines.append(
            f"| {mode} | {len(idx)} | {_mean([cold[i].calls for i in idx]):.1f} → "
            f"{_mean([warm[i].calls for i in idx]):.1f} "
            f"| {_mean([cold[i].input_tokens for i in idx]):,.0f} → "
            f"{_mean([warm[i].input_tokens for i in idx]):,.0f} | {judge} |"
        )
    return "\n".join(lines) + "\n"
