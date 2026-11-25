"""Freshness check: re-run a trail's search on a sample of recalls to catch newer, better nodes."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from ragtrail.models import Trajectory

SearchFn = Callable[[str], Sequence[str]]


@dataclass(frozen=True)
class FreshnessCheck:
    """Re-search a trail's original question on `sample_rate` of the recalls that would serve it.

    `search(query)` is the caller's own retrieval: it returns node ids, best first. A sampled trail is
    marked stale when a node it never saw ranks above every node it cited. Each check costs one search,
    so a lower rate keeps more of what the trail saves. `draw` returns a float in [0, 1).

    >>> check = FreshnessCheck(search=lambda q: ["n90", "n33"], sample_rate=0.25)
    >>> check.sample_rate
    0.25
    """

    search: SearchFn
    sample_rate: float = 0.1
    draw: Callable[[], float] = field(default=random.random, repr=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ValueError(f"sample_rate must be in [0, 1]: {self.sample_rate}")

    def sampled(self) -> bool:
        """Whether this recall pays for a re-search.

        >>> FreshnessCheck(search=lambda q: [], sample_rate=1.0).sampled()
        True
        >>> FreshnessCheck(search=lambda q: [], sample_rate=0.0).sampled()
        False
        """
        return self.draw() < self.sample_rate

    def outranked(self, trajectory: Trajectory) -> bool:
        """Re-run the trail's question and report whether a new node now ranks above the cited ones.

        A node is new when the trail neither cited it nor got it back from any recorded step. When no cited
        node comes back at all, any new node in the results counts as outranking them.

        >>> from datetime import timedelta
        >>> from ragtrail.models import NodeRef
        >>> t = Trajectory.expiring_in(
        ...     timedelta(days=1), scope="acme", query="rotate a token",
        ...     query_norm="rotate token", signature=[1], outcome="verified",
        ...     useful=[NodeRef(node_id="n33", content_hash="h")],
        ... )
        >>> FreshnessCheck(search=lambda q: ["n90", "n33"]).outranked(t)
        True
        >>> FreshnessCheck(search=lambda q: ["n33", "n90"]).outranked(t)
        False
        """
        return outranked(trajectory, self.search(trajectory.query))


def outranked(trajectory: Trajectory, ranked: Sequence[str]) -> bool:
    """Whether a node unknown to `trajectory` comes before its first cited node in `ranked`.

    >>> from datetime import timedelta
    >>> from ragtrail.models import NodeRef, Step
    >>> t = Trajectory.expiring_in(
    ...     timedelta(days=1), scope="acme", query="q", query_norm="q", signature=[1], outcome="verified",
    ...     steps=[Step(tool="search", returned=["n12", "n33"])],
    ...     useful=[NodeRef(node_id="n33", content_hash="h")],
    ... )
    >>> outranked(t, ["n12", "n33", "n90"]), outranked(t, ["n90", "n33"]), outranked(t, ["n12"])
    (False, True, False)
    """
    cited = {r.node_id for r in trajectory.useful}
    known = cited.union(*(s.returned for s in trajectory.steps))
    for node_id in ranked:
        if node_id in cited:
            return False
        if node_id not in known:
            return True
    return False
