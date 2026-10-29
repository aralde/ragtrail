"""`recall`: match → validate hashes → decide mode → render within a token budget."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ragtrail.match import DEFAULT_CONFIG, MatchConfig, band_keys, normalize_query, signature, similarity
from ragtrail.models import Mode, NodeRef, RecallResult, Trajectory
from ragtrail.resolver import NodeResolver, estimate_tokens
from ragtrail.store import TrajectoryStore

DEFAULT_BUDGET_TOKENS = 1500

Estimator = Callable[[str], int]


def _miss(similarity_: float = 0.0) -> RecallResult:
    return RecallResult(mode="miss", trajectory_id=None, similarity=similarity_, rendered="")


def node_line(resolver: NodeResolver, node_id: str) -> str:
    """One-line reference to a node: `label [id]`, or `[id]` when the label is just the id.

    >>> from ragtrail.resolver import GenericResolver
    >>> r = GenericResolver(lambda i: "h", lambda i, n: "", lambda i: "Auth › Tokens")
    >>> node_line(r, "n33")
    'Auth › Tokens [n33]'
    """
    label = resolver.label(node_id)
    return f"[{node_id}]" if not label or label == node_id else f"{label} [{node_id}]"


def _rank(candidates: Sequence[Trajectory], sig: Sequence[int]) -> list[tuple[float, Trajectory]]:
    scored = [(similarity(sig, t.signature), t) for t in candidates if len(t.signature) == len(sig)]
    return sorted(scored, key=lambda st: (-st[0], -st[1].hits, -st[1].created_at.timestamp(), st[1].id))


def _fit_lines(lines: list[str], budget: int, estimator: Estimator, noun: str) -> list[str]:
    """Keep leading lines within `budget`; collapse the rest into one `+N more` line."""
    kept: list[str] = []
    used = 0
    for i, line in enumerate(lines):
        rest = len(lines) - i - 1
        tail = estimator(f"    (+{rest} more {noun})\n") if rest else 0
        cost = estimator(line + "\n")
        if used + cost + tail > budget:
            remaining = len(lines) - i
            return [*kept, f"    (+{remaining} more {noun})"]
        kept.append(line)
        used += cost
    return kept


def render(
    mode: Mode,
    sim: float,
    valid: Sequence[NodeRef],
    changed: Sequence[str],
    resolver: NodeResolver,
    budget_tokens: int,
    estimator: Estimator = estimate_tokens,
) -> tuple[Mode, str]:
    """Render the recall text for `hint` or `prefetch`, collapsing (never cutting) nodes that do not fit.

    Returns the effective mode: a `prefetch` where no node text fits the budget is rendered as a `hint`.
    """
    first = valid[0].node_id

    def header(m: Mode) -> str:
        return f"ragtrail: similar question solved before (similarity {sim:.2f}, mode={m})"

    changed_line = (
        "  Changed since: " + ", ".join(node_line(resolver, n) for n in changed) + " (skipped)"
        if changed
        else ""
    )

    if mode == "prefetch":
        footer = "\nAnswer from these nodes; search only if something is missing."
        fixed = estimator("\n".join([header(mode), "  Prefetched nodes (still valid):", footer]) + "\n")
        remaining = budget_tokens - fixed
        blocks: list[str] = []
        skipped: list[str] = []
        for ref in valid:
            if remaining <= 0:
                skipped.append(ref.node_id)
                continue
            text = resolver.read(ref.node_id, remaining).strip()
            block = f"\n--- {node_line(resolver, ref.node_id)}\n{text}\n"
            cost = estimator(block)
            if cost <= remaining:
                blocks.append(block)
                remaining -= cost
            else:
                skipped.append(ref.node_id)
        if blocks:
            refs = [f"    {node_line(resolver, n)}" for n in skipped]
            more = _fit_lines(refs, remaining - estimator("  Not prefetched (budget):\n"), estimator, "nodes")
            parts = [header(mode), "  Prefetched nodes (still valid):", *blocks]
            if more:
                parts += ["  Not prefetched (budget):", *more]
            parts.append(footer)
            return mode, "\n".join(p.rstrip("\n") for p in parts)
        mode = "hint"

    footer = f'Start with read("{first}") before searching.'
    fixed_parts = [header(mode), "  Useful nodes still valid:", footer]
    if changed_line:
        fixed_parts.append(changed_line)
    remaining = budget_tokens - estimator("\n".join(fixed_parts) + "\n")
    lines = _fit_lines(
        [f"    {node_line(resolver, r.node_id)}" for r in valid], remaining, estimator, "nodes"
    )
    parts = [header(mode), "  Useful nodes still valid:", *lines]
    if changed_line:
        parts.append(changed_line)
    parts.append(footer)
    return mode, "\n".join(parts)


def recall(
    store: TrajectoryStore,
    resolver: NodeResolver,
    query: str,
    scope: str,
    *,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    config: MatchConfig = DEFAULT_CONFIG,
    estimator: Estimator = estimate_tokens,
    allow_prefetch: bool = True,
) -> RecallResult:
    """Find a trajectory for a similar past question in `scope` and hand back its still-valid path.

    - `prefetch`: similarity ≥ `prefetch_threshold` and every useful node unchanged; node texts included.
    - `hint`: similarity ≥ `hint_threshold`, or some nodes changed; lists only still-valid nodes.
    - `miss`: nothing similar, or every useful node changed (that trajectory is marked stale).

    `allow_prefetch=False` caps the mode at `hint` (for resolvers that cannot read node text).

    >>> from ragtrail.recorder import Recorder
    >>> from ragtrail.resolver import GenericResolver, text_hash
    >>> from ragtrail.store import SQLiteStore
    >>> docs = {"n33": "Tokens expire after one hour."}
    >>> resolver = GenericResolver(lambda i: text_hash(docs[i]) if i in docs else None, lambda i, n: docs[i])
    >>> store = SQLiteStore(":memory:")
    >>> rec = Recorder(store, resolver, scope="acme", query="When do access tokens expire?")
    >>> rec.cite(["n33"]); _ = rec.commit("verified")
    >>> recall(store, resolver, "when do the access tokens expire", "acme").mode
    'prefetch'
    >>> recall(store, resolver, "when do the access tokens expire", "globex").mode
    'miss'
    """
    if budget_tokens < 1:
        raise ValueError(f"budget_tokens must be >= 1: {budget_tokens}")
    query_norm = normalize_query(query, config)
    if not query_norm:
        return _miss()
    sig = signature(query_norm, config)
    ranked = _rank(store.candidates(scope, band_keys(scope, sig, config)), sig)
    best_sim = ranked[0][0] if ranked else 0.0
    for sim, trajectory in ranked:
        if sim < config.hint_threshold:
            break
        valid = [r for r in trajectory.useful if resolver.content_hash(r.node_id) == r.content_hash]
        changed = [r.node_id for r in trajectory.useful if r not in valid]
        if not valid:
            store.mark_stale(scope, trajectory.id)
            continue
        full = allow_prefetch and sim >= config.prefetch_threshold and not changed
        wanted: Mode = "prefetch" if full else "hint"
        mode, rendered = render(wanted, sim, valid, changed, resolver, budget_tokens, estimator)
        store.incr_hits(scope, trajectory.id)
        return RecallResult(
            mode=mode,
            trajectory_id=trajectory.id,
            similarity=sim,
            nodes=valid,
            stale=changed,
            rendered=rendered,
        )
    return _miss(best_sim)
