"""Export a stable trail as a hash-checked fetch script that replaces an agent retrieval turn.

The script holds only the trail's node ids and the content hashes they were cited with (never an answer).
Run it: exit 0 prints the cited documents as JSON; exit 3 means a node changed, vanished or the trail
expired, and the caller should fall back to the agent. A model still writes the answer.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from ragtrail.match import DEFAULT_CONFIG, MatchConfig, band_keys, normalize_query, signature, similarity
from ragtrail.models import NodeRef, Trajectory
from ragtrail.resolver import NodeResolver
from ragtrail.store import TrajectoryStore, utc_now

DEFAULT_MAX_TOKENS = 1500
EXIT_CHANGED = 3
EXIT_RESOLVER = 2
UNVERIFIED_HASH = "unverified"


class TrailChanged(Exception):
    """The trail can no longer be served as is: some nodes changed or vanished, or it expired."""

    def __init__(self, changed: Sequence[str], *, expired: bool = False) -> None:
        self.changed = list(changed)
        self.expired = expired
        super().__init__("expired" if expired else "changed: " + ", ".join(self.changed))


@dataclass(frozen=True)
class Document:
    """One cited node as the fetch script returns it."""

    node_id: str
    label: str
    content_hash: str
    text: str


def fetch(
    resolver: NodeResolver,
    nodes: Sequence[NodeRef],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    expires_at: datetime | None = None,
    now: datetime | None = None,
) -> list[Document]:
    """Read `nodes` through `resolver`, or raise `TrailChanged` if any hash differs or the trail expired.

    Every hash is checked before any text is read, so a failure returns nothing partial.

    >>> from ragtrail.resolver import GenericResolver, text_hash
    >>> docs = {"n1": "Limit: 100 requests per minute."}
    >>> r = GenericResolver(lambda i: text_hash(docs[i]) if i in docs else None, lambda i, n: docs[i])
    >>> ref = NodeRef(node_id="n1", content_hash=text_hash(docs["n1"]))
    >>> fetch(r, [ref])[0].text
    'Limit: 100 requests per minute.'
    >>> docs["n1"] = "Limit: 50 requests per minute."
    >>> fetch(r, [ref])
    Traceback (most recent call last):
    ...
    ragtrail.export.TrailChanged: changed: n1
    """
    if expires_at is not None and (now or utc_now()) >= expires_at:
        raise TrailChanged([], expired=True)
    changed = [r.node_id for r in nodes if resolver.content_hash(r.node_id) != r.content_hash]
    if changed:
        raise TrailChanged(changed)
    return [
        Document(r.node_id, resolver.label(r.node_id), r.content_hash, resolver.read(r.node_id, max_tokens))
        for r in nodes
    ]


def export_problems(trajectory: Trajectory, resolver: NodeResolver) -> list[str]:
    """Reasons `trajectory` cannot be exported as a fetch script; empty if it can.

    A trail is exportable when it is not stale, has no rejected answer, cites verified hashes and every
    cited node still has the hash it was cited with.
    """
    problems = []
    if not trajectory.useful:
        problems.append("it cites no nodes")
    if trajectory.stale:
        problems.append("it is stale")
    if trajectory.rejections:
        problems.append(f"its answer was rejected {trajectory.rejections} time(s)")
    if any(r.content_hash == UNVERIFIED_HASH for r in trajectory.useful):
        problems.append("it was recorded without an index (unverified hashes)")
    changed = [r.node_id for r in trajectory.useful if resolver.content_hash(r.node_id) != r.content_hash]
    if changed:
        problems.append("nodes changed since it was recorded: " + ", ".join(changed))
    return problems


def find_trail(
    store: TrajectoryStore,
    resolver: NodeResolver,
    query: str,
    scope: str,
    *,
    config: MatchConfig = DEFAULT_CONFIG,
) -> Trajectory | None:
    """The exportable trail most similar to `query` at prefetch level, without touching hit counters.

    >>> from ragtrail.recorder import Recorder
    >>> from ragtrail.resolver import GenericResolver, text_hash
    >>> from ragtrail.store import SQLiteStore
    >>> r = GenericResolver(lambda i: text_hash("x"), lambda i, n: "x")
    >>> store = SQLiteStore(":memory:")
    >>> rec = Recorder(store, r, scope="acme", query="What are the rate limits?")
    >>> rec.cite(["n1"]); t = rec.commit("verified")
    >>> find_trail(store, r, "what are the rate limits", "acme").id == t.id
    True
    """
    query_norm = normalize_query(query, config)
    if not query_norm:
        return None
    sig = signature(query_norm, config)
    scored = [
        (similarity(sig, t.signature), t)
        for t in store.candidates(scope, band_keys(scope, sig, config))
        if len(t.signature) == len(sig)
    ]
    scored.sort(key=lambda st: (-st[0], -st[1].hits, -st[1].created_at.timestamp(), st[1].id))
    for score, trajectory in scored:
        if score < config.prefetch_threshold:
            break
        if not export_problems(trajectory, resolver):
            return trajectory
    return None


def export_script(
    trajectory: Trajectory,
    *,
    resolver: str | None = None,
    subforest: Path | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Source of the fetch script for `trajectory`; the same inputs always give the same bytes.

    The script rebuilds the resolver from `resolver` (`module:factory`) or `subforest` (corpus DB path).

    >>> from datetime import UTC, datetime, timedelta
    >>> t = Trajectory.expiring_in(
    ...     timedelta(days=30), now=datetime(2026, 1, 1, tzinfo=UTC), id="t1", scope="acme",
    ...     query="What are the rate limits?", query_norm="rate limit", signature=[1], outcome="verified",
    ...     useful=[NodeRef(node_id="n1", content_hash="ab12")],
    ... )
    >>> print(export_script(t, resolver="app.index:resolver").splitlines()[-1])
        sys.exit(run(TRAIL_ID, NODES, EXPIRES_AT, RESOLVER, SUBFOREST, MAX_TOKENS))
    """
    if (resolver is None) == (subforest is None):
        raise ValueError("pass exactly one of resolver or subforest")
    nodes = "".join(f"    ({r.node_id!r}, {r.content_hash!r}),\n" for r in trajectory.useful)
    sub = None if subforest is None else str(subforest.resolve())
    return (
        "#!/usr/bin/env python3\n"
        f'"""ragtrail fetch script for trail {trajectory.id} (exported by `ragtrail export`).\n'
        "\n"
        "Prints the trail's cited documents as JSON on stdout (exit 0). Exit 3: a node changed, vanished or\n"
        "the trail expired; fall back to the agent. Exit 2: the resolver could not be loaded.\n"
        '"""\n'
        "\n"
        "import sys\n"
        "\n"
        "from ragtrail.export import run\n"
        "\n"
        f"TRAIL_ID = {trajectory.id!r}\n"
        f"SCOPE = {trajectory.scope!r}\n"
        f"QUERY = {trajectory.query!r}\n"
        f"EXPIRES_AT = {trajectory.expires_at.isoformat()!r}\n"
        f"RESOLVER = {resolver!r}\n"
        f"SUBFOREST = {sub!r}\n"
        f"MAX_TOKENS = {max_tokens!r}\n"
        f"NODES = [\n{nodes}]\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    sys.exit(run(TRAIL_ID, NODES, EXPIRES_AT, RESOLVER, SUBFOREST, MAX_TOKENS))\n"
    )


def open_resolver(resolver: str | None, subforest: str | Path | None) -> NodeResolver:
    """Build the resolver from a `module:factory` spec or a subforest corpus DB path."""
    from ragtrail.cli import load_resolver, subforest_resolver

    if subforest is not None:
        path = Path(subforest)
        if not path.exists():
            raise RuntimeError(f"{path} does not exist")
        return subforest_resolver(path)
    if resolver is None:
        raise ValueError("no resolver given")
    return load_resolver(resolver)


def run(
    trail_id: str,
    nodes: Sequence[tuple[str, str]],
    expires_at: str,
    resolver: str | None,
    subforest: str | None,
    max_tokens: int,
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Body of an exported fetch script; returns its exit code (0 ok, 2 resolver error, 3 changed)."""
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        active = open_resolver(resolver, subforest)
    except (RuntimeError, ValueError, TypeError, ImportError, AttributeError) as exc:
        print(f"ragtrail: cannot load the resolver: {exc}", file=err)
        return EXIT_RESOLVER
    refs = [NodeRef(node_id=n, content_hash=h) for n, h in nodes]
    try:
        documents = fetch(active, refs, max_tokens=max_tokens, expires_at=datetime.fromisoformat(expires_at))
    except TrailChanged as exc:
        print(f"ragtrail: trail {trail_id} {exc}; fall back to the agent", file=err)
        return EXIT_CHANGED
    json.dump({"trail": trail_id, "documents": [asdict(d) for d in documents]}, out, ensure_ascii=False)
    out.write("\n")
    return 0
