"""Framework-agnostic middleware: wrap one agent turn in `with turn(...) as t:`."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

from ragtrail.match import DEFAULT_CONFIG, MatchConfig
from ragtrail.models import Outcome, RecallResult, Trajectory
from ragtrail.recall import DEFAULT_BUDGET_TOKENS, recall
from ragtrail.recorder import DEFAULT_TTL, Recorder
from ragtrail.resolver import NodeResolver
from ragtrail.store import Clock, TrajectoryStore, utc_now


class Turn:
    """One agent turn: the recall result up front, then steps and citations, committed on exit.

    Set `outcome` (or call `accept()`) before the block ends; without it nothing is stored.
    """

    def __init__(self, recall_result: RecallResult, recorder: Recorder) -> None:
        self.recall = recall_result
        self.outcome: Outcome | None = None
        self.trajectory: Trajectory | None = None
        self._recorder = recorder

    def step(self, tool: str, args: Mapping[str, Any] | None = None, returned: Iterable[str] = ()) -> None:
        """Record one tool call and the node ids it returned."""
        self._recorder.step(tool, args, returned)

    def cite(self, node_ids: Iterable[str]) -> None:
        """Mark nodes the answer cites."""
        self._recorder.cite(node_ids)

    def accept(self, outcome: Outcome = "accepted") -> None:
        """Mark the turn as successful so it is recorded on exit."""
        self.outcome = outcome


@contextmanager
def turn(
    store: TrajectoryStore,
    resolver: NodeResolver,
    scope: str,
    query: str,
    *,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    config: MatchConfig = DEFAULT_CONFIG,
    ttl: timedelta = DEFAULT_TTL,
    clock: Clock = utc_now,
) -> Iterator[Turn]:
    """Recall on entry, record on exit. An exception inside the block drops the turn and propagates.

    >>> from ragtrail.resolver import GenericResolver, text_hash
    >>> from ragtrail.store import SQLiteStore
    >>> docs = {"c7": "Tokens expire after one hour."}
    >>> resolver = GenericResolver(lambda i: text_hash(docs[i]) if i in docs else None, lambda i, n: docs[i])
    >>> store = SQLiteStore(":memory:")
    >>> with turn(store, resolver, "acme", "When do tokens expire?") as t:
    ...     t.recall.mode
    ...     t.step("search", {"q": "token expiry"}, returned=["c7"])
    ...     t.cite(["c7"])
    ...     t.accept("verified")
    'miss'
    >>> with turn(store, resolver, "acme", "when do the tokens expire") as t:
    ...     t.recall.mode
    'prefetch'
    """
    result = recall(store, resolver, query, scope, budget_tokens=budget_tokens, config=config)
    recorder = Recorder(store, resolver, scope, query, config=config, ttl=ttl, clock=clock)
    t = Turn(result, recorder)
    try:
        yield t
    except BaseException:
        recorder.commit(None)
        raise
    t.trajectory = recorder.commit(t.outcome)
