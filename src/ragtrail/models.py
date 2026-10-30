"""Data model: trajectories are paths (queries, steps, node ids, hashes), never answers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Outcome = Literal["verified", "feedback", "accepted"]
Mode = Literal["prefetch", "hint", "miss"]

KEY_SEPARATOR = "#"


def _check_key_segment(value: str, name: str) -> str:
    if not value:
        raise ValueError(f"{name} must not be empty")
    if KEY_SEPARATOR in value:
        raise ValueError(f"{name} must not contain {KEY_SEPARATOR!r}: {value!r}")
    return value


def new_trajectory_id() -> str:
    """Return a fresh random trajectory id (32 hex chars).

    >>> len(new_trajectory_id())
    32
    """
    return uuid.uuid4().hex


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NodeRef(_Frozen):
    """A node (section, chunk or doc) the agent used, pinned to the content hash it saw.

    >>> NodeRef(node_id="n33", content_hash="ab12").node_id
    'n33'
    """

    node_id: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)


class Step(_Frozen):
    """One tool call in an agent turn: what it ran and which node ids came back.

    >>> Step(tool="search", args={"q": "refresh tokens"}, returned=["n33", "n35"]).returned
    ['n33', 'n35']
    """

    tool: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    returned: list[str] = Field(default_factory=list)


class Trajectory(_Frozen):
    """The retrieval path of one accepted agent turn, scoped and with an expiry.

    `stale` is set by the store when every useful node changed; stale trajectories are kept
    (for `get` and debugging) but never returned as candidates. `embedding` (with the `embed_model` that
    produced it) is only set when an embedder was used at record time.

    >>> from datetime import datetime, timedelta, UTC
    >>> now = datetime(2026, 1, 1, tzinfo=UTC)
    >>> t = Trajectory(
    ...     scope="acme", query="How do I refresh a token?", query_norm="refresh token",
    ...     signature=[1, 2, 3], outcome="verified", created_at=now, expires_at=now + timedelta(days=30),
    ... )
    >>> t.hits, t.stale
    (0, False)
    """

    id: str = Field(default_factory=new_trajectory_id)
    scope: str
    query: str
    query_norm: str
    signature: list[int]
    steps: list[Step] = Field(default_factory=list)
    useful: list[NodeRef] = Field(default_factory=list)
    outcome: Outcome
    created_at: AwareDatetime
    expires_at: AwareDatetime
    hits: int = Field(default=0, ge=0)
    stale: bool = False
    embedding: list[float] | None = None
    embed_model: str | None = None

    @field_validator("id")
    @classmethod
    def _id_is_key_safe(cls, value: str) -> str:
        return _check_key_segment(value, "id")

    @field_validator("scope")
    @classmethod
    def _scope_is_key_safe(cls, value: str) -> str:
        return _check_key_segment(value, "scope")

    @model_validator(mode="after")
    def _expires_after_creation(self) -> Trajectory:
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        return self

    @classmethod
    def expiring_in(cls, ttl: timedelta, *, now: datetime | None = None, **fields: Any) -> Trajectory:
        """Build a trajectory created at `now` (default: current UTC time) that expires after `ttl`.

        >>> t = Trajectory.expiring_in(
        ...     timedelta(days=7), scope="acme", query="q", query_norm="q", signature=[1], outcome="accepted"
        ... )
        >>> t.expires_at - t.created_at
        datetime.timedelta(days=7)
        """
        created = now or datetime.now(UTC)
        return cls(created_at=created, expires_at=created + ttl, **fields)


class RecallResult(_Frozen):
    """What `recall` hands back to the agent: the mode, the still-valid nodes and the rendered text.

    >>> RecallResult(mode="miss", trajectory_id=None, similarity=0.0, rendered="").nodes
    []
    """

    mode: Mode
    trajectory_id: str | None
    similarity: float = Field(ge=0.0, le=1.0)
    nodes: list[NodeRef] = Field(default_factory=list)
    stale: list[str] = Field(default_factory=list)
    rendered: str
    matched_by: Literal["lexical", "embedding"] | None = None
