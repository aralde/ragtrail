"""`Recorder`: collects one agent turn and writes it only if the turn has a positive outcome."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import timedelta
from typing import Any

from ragtrail.embed import DEFAULT_EMBED_CONFIG, EmbedConfig, Embedder, embed_band_keys, normalize_vector
from ragtrail.match import DEFAULT_CONFIG, MatchConfig, band_keys, normalize_query, signature
from ragtrail.models import NodeRef, Outcome, Step, Trajectory
from ragtrail.resolver import NodeResolver
from ragtrail.store import Clock, TrajectoryStore, utc_now

DEFAULT_TTL = timedelta(days=30)


class Recorder:
    """Records the steps and citations of one turn; `commit` applies the admission policy.

    Admission: nothing is written unless `commit` gets an outcome (`"verified"`, `"feedback"` or
    `"accepted"`), the query normalizes to something, and at least one cited node still resolves.

    >>> from ragtrail.resolver import GenericResolver, text_hash
    >>> from ragtrail.store import SQLiteStore
    >>> docs = {"n33": "Tokens expire after one hour."}
    >>> resolver = GenericResolver(lambda i: text_hash(docs[i]) if i in docs else None, lambda i, n: docs[i])
    >>> store = SQLiteStore(":memory:")
    >>> rec = Recorder(store, resolver, scope="acme", query="When do tokens expire?")
    >>> rec.step("search", {"q": "token expiry"}, returned=["n33"])
    >>> rec.cite(["n33"])
    >>> t = rec.commit("verified")
    >>> [n.node_id for n in t.useful]
    ['n33']
    >>> Recorder(store, resolver, scope="acme", query="q").commit(None) is None
    True
    """

    def __init__(
        self,
        store: TrajectoryStore,
        resolver: NodeResolver,
        scope: str,
        query: str,
        *,
        config: MatchConfig = DEFAULT_CONFIG,
        ttl: timedelta = DEFAULT_TTL,
        clock: Clock = utc_now,
        embedder: Embedder | None = None,
        embed_config: EmbedConfig = DEFAULT_EMBED_CONFIG,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError(f"ttl must be positive: {ttl}")
        self.store = store
        self.resolver = resolver
        self.scope = scope
        self.query = query
        self.config = config
        self.ttl = ttl
        self.clock = clock
        self.embedder = embedder
        self.embed_config = embed_config
        self.steps: list[Step] = []
        self.cited: list[str] = []
        self.committed = False

    def step(self, tool: str, args: Mapping[str, Any] | None = None, returned: Iterable[str] = ()) -> None:
        """Record one tool call and the node ids it returned."""
        self._check_open()
        self.steps.append(Step(tool=tool, args=dict(args or {}), returned=list(returned)))

    def cite(self, node_ids: Iterable[str]) -> None:
        """Mark nodes as useful (cited by the answer). Order is kept; duplicates are ignored."""
        self._check_open()
        for node_id in node_ids:
            if node_id not in self.cited:
                self.cited.append(node_id)

    def commit(self, outcome: Outcome | None) -> Trajectory | None:
        """Write the trajectory if admitted and return it; return `None` if the turn was dropped."""
        self._check_open()
        self.committed = True
        if outcome is None:
            return None
        query_norm = normalize_query(self.query, self.config)
        if not query_norm:
            return None
        useful = []
        for node_id in self.cited:
            content_hash = self.resolver.content_hash(node_id)
            if content_hash is not None:
                useful.append(NodeRef(node_id=node_id, content_hash=content_hash))
        if not useful:
            return None
        sig = signature(query_norm, self.config)
        keys = band_keys(self.scope, sig, self.config)
        vector = None
        if self.embedder is not None:
            vector = normalize_vector(self.embedder.embed([self.query])[0])
            keys += embed_band_keys(self.scope, vector, self.embed_config)
        trajectory = Trajectory.expiring_in(
            self.ttl,
            now=self.clock(),
            scope=self.scope,
            query=self.query,
            query_norm=query_norm,
            signature=sig,
            steps=self.steps,
            useful=useful,
            outcome=outcome,
            embedding=vector,
            embed_model=self.embedder.name if self.embedder else None,
        )
        self.store.put(trajectory, keys)
        return trajectory

    def _check_open(self) -> None:
        if self.committed:
            raise RuntimeError("this turn was already committed")
