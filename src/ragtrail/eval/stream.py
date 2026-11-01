"""Offline robustness evals (no LLM): corpus edits after recording, and a mixed traffic stream.

- `edit_rows`: warm a store, then edit a random share of the cited nodes and replay the repeat questions.
  Compares ragtrail (hash-validated pointers) with a copy cache (stores the cited text, TTL only, like
  MERMAIDS) and a pointer cache without validation (stores ids, like a retrieval-result cache).
- `build_stream` + `run_stream`: start from an empty cache and play new questions interleaved with
  paraphrased repeats at a chosen rate, recording an oracle trail after each answer, as live traffic would.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal

from ragtrail.embed import Embedder
from ragtrail.eval.data import EvalQuestion
from ragtrail.eval.offline import warm_up
from ragtrail.eval.stats import wilson
from ragtrail.models import Mode
from ragtrail.recall import recall
from ragtrail.resolver import NodeResolver
from ragtrail.store import TrajectoryStore

Kind = Literal["new", "sibling", "repeat"]
DocOf = Callable[[str], str | None]


class EditedResolver:
    """Wraps a resolver so that `edited` nodes report a new content hash and `deleted` nodes vanish.

    >>> from ragtrail.resolver import GenericResolver
    >>> base = GenericResolver(lambda i: "h", lambda i, n: "text")
    >>> r = EditedResolver(base, edited={"a"}, deleted={"b"})
    >>> r.content_hash("a"), r.content_hash("b"), r.content_hash("c")
    ('h:edited', None, 'h')
    """

    def __init__(
        self, base: NodeResolver, edited: AbstractSet[str], deleted: AbstractSet[str] = frozenset()
    ) -> None:
        self.base = base
        self.edited = edited
        self.deleted = deleted

    def content_hash(self, node_id: str) -> str | None:
        if node_id in self.deleted:
            return None
        h = self.base.content_hash(node_id)
        return None if h is None else f"{h}:edited" if node_id in self.edited else h

    def label(self, node_id: str) -> str:
        return self.base.label(node_id)

    def read(self, node_id: str, max_tokens: int) -> str:
        return self.base.read(node_id, max_tokens)


def _hit_gold(nodes: Sequence[str], gold: Sequence[str], doc_of: DocOf | None) -> bool:
    return any(n in gold or (doc_of is not None and doc_of(n) in gold) for n in nodes)


@dataclass(frozen=True)
class EditRow:
    """One repeat question under one edit rate."""

    id: str
    rate: float
    base_mode: Mode
    base_nodes: tuple[str, ...]
    mode: Mode
    nodes: tuple[str, ...]
    changed: int
    served_changed: int

    @property
    def base_hit(self) -> bool:
        return self.base_mode != "miss"


def edit_rows(
    fresh_store: Callable[[], TrajectoryStore],
    resolver: NodeResolver,
    questions: Sequence[tuple[EvalQuestion, str]],
    cited: Sequence[str],
    rates: Sequence[float],
    *,
    budget_tokens: int = 2000,
    embedder: Embedder | None = None,
    seed: int = 7,
) -> list[EditRow]:
    """For each rate, edit that share of `cited` (seeded) and replay `questions` (question, scope) on a
    freshly warmed store from `fresh_store()`. Rate 0 is the baseline every rate is compared against.

    >>> from ragtrail.resolver import GenericResolver
    >>> from ragtrail.store import SQLiteStore
    >>> r = GenericResolver(lambda i: "h", lambda i, n: "text")
    >>> w = EvalQuestion(id="w", split="s", question="How do I add a domain?", answer="", gold=["n1", "n2"])
    >>> def fresh():
    ...     store = SQLiteStore(":memory:"); warm_up(store, r, [w], "s"); return store
    >>> q = w.model_copy(update={"id": "t", "question": "how do i add a domain"})
    >>> rows = edit_rows(fresh, r, [(q, "s")], ["n1", "n2"], [0.0, 0.5, 1.0])
    >>> [(row.rate, row.mode, row.changed) for row in rows]
    [(0.0, 'prefetch', 0), (0.5, 'hint', 1), (1.0, 'miss', 2)]
    """
    order = sorted(set(cited))
    random.Random(seed).shuffle(order)
    base: dict[str, tuple[Mode, tuple[str, ...]]] = {}
    rows = []
    for rate in sorted({0.0, *rates}):
        edited = set(order[: round(rate * len(order))])
        store = fresh_store()
        res = EditedResolver(resolver, edited)
        for q, scope in questions:
            result = recall(store, res, q.question, scope, budget_tokens=budget_tokens, embedder=embedder)
            nodes = tuple(n.node_id for n in result.nodes)
            if rate == 0:
                base[q.id] = (result.mode, nodes)
            base_mode, base_nodes = base[q.id]
            rows.append(
                EditRow(
                    id=q.id,
                    rate=rate,
                    base_mode=base_mode,
                    base_nodes=base_nodes,
                    mode=result.mode,
                    nodes=nodes,
                    changed=sum(n in edited for n in base_nodes),
                    served_changed=sum(n in edited for n in nodes),
                )
            )
    return [r for r in rows if r.rate in rates]


def edit_markdown(rows: Sequence[EditRow]) -> str:
    """Per edit rate: what each cache design serves on the questions that hit before any edit."""
    lines = [
        "| Share of cited nodes edited | Hits before edits | Copy cache: hits serving old text "
        "| Pointer cache, no validation: hits with silently changed nodes "
        "| ragtrail: prefetch / hint / miss | ragtrail: hits serving changed nodes |",
        "|---|---|---|---|---|---|",
    ]
    for rate in sorted({r.rate for r in rows}):
        sel = [r for r in rows if r.rate == rate and r.base_hit]
        stale = sum(r.changed > 0 for r in sel)
        modes = {m: sum(r.mode == m for r in sel) for m in ("prefetch", "hint", "miss")}
        served_changed = sum(r.mode != "miss" and r.served_changed > 0 for r in sel)
        lines.append(
            f"| {rate:.0%} | {len(sel)} | {_pct(stale, len(sel))} | {_pct(stale, len(sel))} "
            f"| {modes['prefetch']} / {modes['hint']} / {modes['miss']} | {served_changed} |"
        )
    return "\n".join(lines) + "\n"


def _pct(k: int, n: int) -> str:
    if not n:
        return "—"
    lo, hi = wilson(k, n)
    return f"{k} = {k / n:.0%} ({lo:.0%} to {hi:.0%})"


@dataclass(frozen=True)
class Event:
    """One question in a traffic stream. `kind`: a first-time question, a first-time question whose scope
    already holds trails of other questions (`sibling`, it should miss), or a paraphrase of an earlier one."""

    question: EvalQuestion
    scope: str
    kind: Kind


def build_stream(
    new: Sequence[tuple[EvalQuestion, str]],
    paraphrases: Sequence[EvalQuestion],
    repeat_rate: float,
    seed: int = 7,
) -> list[Event]:
    """Shuffle `new` (question, scope) and insert paraphrases (matched by `source_id`) at random points
    after their source so that repeats are `repeat_rate` of the stream. When there are too few paraphrases,
    new questions that are not paraphrase sources are dropped until the rate holds.

    >>> qs = [(EvalQuestion(id=f"q{i}", split="s", question=f"q{i}", answer=""), "s") for i in range(8)]
    >>> ps = [EvalQuestion(id=f"p{i}", split="p", question="p", answer="", source_id=f"q{i}") for i in "01"]
    >>> events = build_stream(qs, ps, 0.25)
    >>> len(events), sum(e.kind == "repeat" for e in events)
    (8, 2)
    >>> all(next(i for i, e in enumerate(events) if e.question.id == p.source_id)
    ...     < next(i for i, e in enumerate(events) if e.question.id == p.id) for p in ps)
    True
    """
    if not 0 <= repeat_rate < 1:
        raise ValueError(f"repeat_rate must be in [0, 1): {repeat_rate}")
    rng = random.Random(seed)
    scope_of = {q.id: s for q, s in new}
    usable = [p for p in paraphrases if p.source_id in scope_of]
    wanted = round(repeat_rate * len(new) / (1 - repeat_rate))
    if wanted > len(usable):
        reps = usable
        sources = {p.source_id for p in reps}
        keep = round(len(reps) * (1 - repeat_rate) / repeat_rate)
        rest = [x for x in new if x[0].id not in sources]
        rng.shuffle(rest)
        pool = [x for x in new if x[0].id in sources] + rest[: max(0, keep - len(sources))]
    else:
        reps = rng.sample(usable, wanted)
        pool = list(new)
    rng.shuffle(pool)
    timed: list[tuple[float, int, Event]] = []
    at = {}
    for i, (q, scope) in enumerate(pool):
        at[q.id] = i
        timed.append((float(i), 0, Event(q, scope, "new")))
    for p in reps:
        start = at[p.source_id or ""]
        timed.append(
            (rng.uniform(start + 0.5, len(pool)), 1, Event(p, scope_of[p.source_id or ""], "repeat"))
        )
    events = [e for _, _, e in sorted(timed, key=lambda t: (t[0], t[1]))]
    seen: set[str] = set()
    out = []
    for e in events:
        kind: Kind = e.kind
        if kind == "new" and e.scope in seen and len({s for _, s in new}) > 1:
            kind = "sibling"
        seen.add(e.scope)
        out.append(Event(e.question, e.scope, kind))
    return out


@dataclass(frozen=True)
class StreamRow:
    """What recall returned for one stream event, before its own trail was recorded."""

    id: str
    kind: Kind
    mode: Mode
    gold_hit: bool


def run_stream(
    store: TrajectoryStore,
    resolver: NodeResolver,
    events: Sequence[Event],
    *,
    budget_tokens: int = 2000,
    embedder: Embedder | None = None,
    doc_of: DocOf | None = None,
) -> list[StreamRow]:
    """Play the stream from whatever `store` holds: recall, score against gold, then record an oracle trail.

    >>> from ragtrail.resolver import GenericResolver
    >>> from ragtrail.store import SQLiteStore
    >>> r = GenericResolver(lambda i: "h", lambda i, n: "text")
    >>> a = EvalQuestion(id="a", split="s", question="How do I add a domain?", answer="", gold=["n1"])
    >>> b = a.model_copy(update={"id": "b", "question": "how do i add a domain", "source_id": "a"})
    >>> rows = run_stream(SQLiteStore(":memory:"), r, [Event(a, "s", "new"), Event(b, "s", "repeat")],
    ...                   budget_tokens=500)
    >>> [(x.kind, x.mode, x.gold_hit) for x in rows]
    [('new', 'miss', False), ('repeat', 'prefetch', True)]
    """
    rows = []
    for e in events:
        result = recall(
            store, resolver, e.question.question, e.scope, budget_tokens=budget_tokens, embedder=embedder
        )
        nodes = [n.node_id for n in result.nodes]
        rows.append(StreamRow(e.question.id, e.kind, result.mode, _hit_gold(nodes, e.question.gold, doc_of)))
        warm_up(store, resolver, [e.question], e.scope, embedder=embedder)
    return rows


def stream_markdown(rows_by_rate: dict[float, list[StreamRow]]) -> str:
    """Per repeat rate and event kind: hits, hits that include gold, hits that do not (false hits)."""
    lines = [
        "| Repeat rate | Event | Questions | Hits (95% CI) | Hits with gold | Hits without gold (95% CI) |",
        "|---|---|---|---|---|---|",
    ]
    for rate, rows in sorted(rows_by_rate.items()):
        for kind in ("repeat", "new", "sibling", "all"):
            sel = rows if kind == "all" else [r for r in rows if r.kind == kind]
            if not sel:
                continue
            hits = [r for r in sel if r.mode != "miss"]
            good = sum(r.gold_hit for r in hits)
            lines.append(
                f"| {rate:.0%} | {kind} | {len(sel)} | {_pct(len(hits), len(sel))} | {good} "
                f"| {_pct(len(hits) - good, len(sel))} |"
            )
    return "\n".join(lines) + "\n"
