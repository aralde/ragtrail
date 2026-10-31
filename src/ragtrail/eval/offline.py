"""Offline eval (no LLM): warm a trail store with oracle trails, then measure what `recall` returns.

Warm-up trails cite each warm-up question's gold documents, as an answer with verified citations would.
For each test question we record the recall mode and whether the recalled nodes include a gold document
("path precision"). Thresholds are swept on a dev pairing that never touches the test split.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ragtrail.embed import DEFAULT_EMBED_CONFIG, Embedder
from ragtrail.eval.data import EvalQuestion
from ragtrail.eval.stats import wilson
from ragtrail.match import DEFAULT_CONFIG, MatchConfig, band_keys, normalize_query, signature, similarity
from ragtrail.models import Mode
from ragtrail.recall import recall
from ragtrail.recorder import Recorder
from ragtrail.resolver import NodeResolver, estimate_tokens
from ragtrail.store import TrajectoryStore

MODES: tuple[Mode, ...] = ("prefetch", "hint", "miss")


def warm_up(
    store: TrajectoryStore,
    resolver: NodeResolver,
    questions: Sequence[EvalQuestion],
    scope: str,
    config: MatchConfig = DEFAULT_CONFIG,
    embedder: Embedder | None = None,
) -> int:
    """Record one oracle trail per question (citing its gold docs); return how many were admitted.

    >>> from ragtrail.store import SQLiteStore
    >>> from ragtrail.resolver import GenericResolver
    >>> r = GenericResolver(lambda i: "h", lambda i, n: "text")
    >>> q = EvalQuestion(id="w1", split="warm", question="How do I add a domain?", answer="", gold=["n5"])
    >>> warm_up(SQLiteStore(":memory:"), r, [q], "eval")
    1
    """
    admitted = 0
    for q in questions:
        rec = Recorder(store, resolver, scope, q.question, config=config, embedder=embedder)
        rec.step("oracle", {"question_id": q.id}, q.gold)
        rec.cite(q.gold)
        admitted += rec.commit("verified") is not None
    return admitted


def warm_from_records(
    store: TrajectoryStore,
    resolver: NodeResolver,
    records: Sequence[dict[str, Any]],
    scope: str,
    config: MatchConfig = DEFAULT_CONFIG,
    embedder: Embedder | None = None,
) -> int:
    """Replay `record` calls an agent made (query, cited, outcome, steps) into `store`; return how many were
    admitted. This builds a warm store from the agent's own citations instead of oracle gold.

    >>> from ragtrail.store import SQLiteStore
    >>> from ragtrail.resolver import GenericResolver
    >>> r = GenericResolver(lambda i: "h" if i == "n5" else None, lambda i, n: "text")
    >>> recs = [{"query": "How do I add a domain?", "cited": ["n5"], "outcome": "accepted"},
    ...         {"query": "Other?", "cited": ["gone"], "outcome": "accepted"}]
    >>> warm_from_records(SQLiteStore(":memory:"), r, recs, "eval")
    1
    """
    admitted = 0
    for record in records:
        rec = Recorder(
            store, resolver, scope, str(record.get("query") or ""), config=config, embedder=embedder
        )
        for step in record.get("steps") or []:
            rec.step(str(step.get("tool", "")), step.get("args") or {}, step.get("returned") or [])
        rec.cite(str(c) for c in record.get("cited") or [])
        admitted += rec.commit(record.get("outcome") or "accepted") is not None
    return admitted


@dataclass(frozen=True)
class RecallRow:
    """What recall returned for one test question."""

    id: str
    mode: Mode
    similarity: float
    nodes: tuple[str, ...]
    gold_hit: bool
    rendered_tokens: int


def recall_rows(
    store: TrajectoryStore,
    resolver: NodeResolver,
    questions: Sequence[EvalQuestion],
    scope: str,
    *,
    budget_tokens: int,
    config: MatchConfig = DEFAULT_CONFIG,
    embedder: Embedder | None = None,
) -> list[RecallRow]:
    """Run `recall` for every question and score whether the recalled nodes include a gold doc."""
    rows = []
    for q in questions:
        result = recall(
            store, resolver, q.question, scope, budget_tokens=budget_tokens, config=config, embedder=embedder
        )
        nodes = tuple(n.node_id for n in result.nodes)
        rows.append(
            RecallRow(
                id=q.id,
                mode=result.mode,
                similarity=result.similarity,
                nodes=nodes,
                gold_hit=bool(set(nodes) & set(q.gold)),
                rendered_tokens=estimate_tokens(result.rendered),
            )
        )
    return rows


def best_matches(
    pool: Sequence[EvalQuestion], queries: Sequence[EvalQuestion], config: MatchConfig = DEFAULT_CONFIG
) -> list[tuple[float, bool]]:
    """For each query, the best LSH candidate's similarity in `pool` and whether they share a gold doc.

    >>> a = EvalQuestion(id="a", split="p", question="reset my password", answer="", gold=["n1"])
    >>> b = EvalQuestion(id="b", split="q", question="how to reset my password", answer="", gold=["n1"])
    >>> sim, same = best_matches([a], [b])[0]
    >>> sim > 0.5, same
    (True, True)
    """
    index: dict[str, list[int]] = {}
    sigs: list[list[int]] = []
    for i, q in enumerate(pool):
        norm = normalize_query(q.question, config)
        sig = signature(norm, config) if norm else []
        sigs.append(sig)
        for key in band_keys("x", sig, config) if sig else []:
            index.setdefault(key, []).append(i)
    out = []
    for q in queries:
        norm = normalize_query(q.question, config)
        if not norm:
            out.append((0.0, False))
            continue
        sig = signature(norm, config)
        cands = {i for key in band_keys("x", sig, config) for i in index.get(key, [])}
        best = max(((similarity(sig, sigs[i]), i) for i in cands), default=(0.0, -1))
        same = best[1] >= 0 and bool(set(q.gold) & set(pool[best[1]].gold))
        out.append((best[0], same))
    return out


def exact_duplicates(pool: Sequence[EvalQuestion], queries: Sequence[EvalQuestion]) -> int:
    """Queries whose normalized text equals some pool question's (a leakage check).

    >>> q = EvalQuestion(id="a", split="p", question="Reset password?", answer="")
    >>> exact_duplicates([q], [q.model_copy(update={"id": "b"})])
    1
    """
    seen = {normalize_query(q.question) for q in pool}
    return sum(normalize_query(q.question) in seen for q in queries)


def sweep_table(matches: Sequence[tuple[float, bool]], thresholds: Sequence[float]) -> list[str]:
    """Markdown rows: for each threshold, how many queries match at or above it and how many share gold."""
    lines = ["| Threshold | Matched | Shares a gold doc | Precision (95% CI) |", "|---|---|---|---|"]
    for t in thresholds:
        sel = [same for sim, same in matches if sim >= t]
        good = sum(sel)
        lo, hi = wilson(good, len(sel))
        prec = f"{good / len(sel):.0%} ({lo:.0%} to {hi:.0%})" if sel else "—"
        lines.append(f"| {t:.2f} | {len(sel)}/{len(matches)} | {good} | {prec} |")
    return lines


@dataclass
class OfflineReport:
    """Everything the offline Markdown report shows for one scenario."""

    scenario: str
    description: str
    warm_count: int
    admitted: int
    test_count: int
    duplicates: int
    rows: list[RecallRow]
    config: MatchConfig
    budget_tokens: int
    dev_matches: list[tuple[float, bool]] | None = None
    dev_label: str = ""
    embed_model: str | None = None

    def markdown(self) -> str:
        """Render as Markdown."""
        n = len(self.rows)
        lines = [
            f"## {self.scenario}",
            "",
            self.description,
            "",
            f"- Warm-up questions: {self.warm_count} ({self.admitted} trails admitted)",
            f"- Test questions: {self.test_count}; exact normalized duplicates of a warm-up question: "
            f"{self.duplicates}",
            f"- Thresholds: hint ≥ {self.config.hint_threshold}, "
            f"prefetch ≥ {self.config.prefetch_threshold}; LSH {self.config.bands}x{self.config.rows}; "
            f"recall budget {self.budget_tokens} tokens",
            f"- Embedding matcher: {self.embed_model} (cosine hint ≥ {DEFAULT_EMBED_CONFIG.hint_threshold}, "
            f"prefetch ≥ {DEFAULT_EMBED_CONFIG.prefetch_threshold}; SimHash {DEFAULT_EMBED_CONFIG.bands}x"
            f"{DEFAULT_EMBED_CONFIG.rows})"
            if self.embed_model
            else "- Embedding matcher: off",
            "",
            "| Mode | Questions | Share | Recalled nodes include gold (95% CI) | Mean similarity "
            "| Mean recall tokens |",
            "|---|---|---|---|---|---|",
        ]
        for mode in MODES:
            sel = [r for r in self.rows if r.mode == mode]
            if not sel:
                lines.append(f"| {mode} | 0 | 0% | — | — | — |")
                continue
            good = sum(r.gold_hit for r in sel)
            lo, hi = wilson(good, len(sel))
            gold = (
                "—" if mode == "miss" else f"{good}/{len(sel)} = {good / len(sel):.0%} ({lo:.0%} to {hi:.0%})"
            )
            lines.append(
                f"| {mode} | {len(sel)} | {len(sel) / n:.0%} | {gold} "
                f"| {statistics.fmean(r.similarity for r in sel):.2f} "
                f"| {statistics.fmean(r.rendered_tokens for r in sel):.0f} |"
            )
        if self.dev_matches is not None:
            lines += ["", f"Threshold sweep on the dev pairing ({self.dev_label}), never on test:", ""]
            lines += sweep_table(self.dev_matches, (0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6))
        return "\n".join(lines) + "\n"
