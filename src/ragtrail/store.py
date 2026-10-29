"""`TrajectoryStore` protocol and the core `SQLiteStore` backend."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from ragtrail.keys import band_key_in_scope, trajectory_key
from ragtrail.models import Trajectory

Clock = Callable[[], datetime]

DEFAULT_BAND_CAP = 32


def utc_now() -> datetime:
    """Current time as an aware UTC datetime.

    >>> utc_now().tzinfo is not None
    True
    """
    return datetime.now(UTC)


@runtime_checkable
class TrajectoryStore(Protocol):
    """Persistence for trajectories and their LSH band buckets.

    Every backend must: keep scopes isolated (a band key outside `scope` is an error), never return
    expired trajectories, never return stale ones from `candidates`, and keep each band bucket capped
    to its newest entries.
    """

    def put(self, trajectory: Trajectory, band_keys: Sequence[str]) -> None:
        """Insert or replace `trajectory` and index it under `band_keys` (all in its scope)."""
        ...

    def get(self, scope: str, trajectory_id: str) -> Trajectory | None:
        """Return the trajectory if it exists and has not expired (stale ones included)."""
        ...

    def candidates(self, scope: str, band_keys: Sequence[str]) -> list[Trajectory]:
        """Union of live, non-stale trajectories in the given band buckets, newest first."""
        ...

    def mark_stale(self, scope: str, trajectory_id: str) -> None:
        """Flag a trajectory as stale so it stops being a candidate. No-op if missing."""
        ...

    def incr_hits(self, scope: str, trajectory_id: str) -> int:
        """Increment the hit counter and return the new value (0 if missing or expired)."""
        ...

    def purge_expired(self) -> int:
        """Delete expired trajectories and their band entries; return how many were deleted."""
        ...


def _check_band_keys(scope: str, band_keys: Sequence[str]) -> None:
    for key in band_keys:
        if not band_key_in_scope(key, scope):
            raise ValueError(f"band key {key!r} is not a band key of scope {scope!r}")


def _ts(value: datetime) -> float:
    return value.timestamp()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS trajectories (
    pk TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    hits INTEGER NOT NULL DEFAULT 0,
    stale INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS trajectories_expires ON trajectories (expires_at);
CREATE TABLE IF NOT EXISTS bands (
    pk TEXT NOT NULL,
    trajectory_pk TEXT NOT NULL REFERENCES trajectories (pk) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    PRIMARY KEY (pk, trajectory_pk)
);
CREATE INDEX IF NOT EXISTS bands_trajectory ON bands (trajectory_pk);
"""


class SQLiteStore:
    """`TrajectoryStore` backed by a single SQLite file (or `":memory:"`).

    >>> from datetime import timedelta
    >>> store = SQLiteStore(":memory:")
    >>> t = Trajectory.expiring_in(
    ...     timedelta(days=1), scope="acme", query="q", query_norm="q", signature=[1], outcome="accepted"
    ... )
    >>> store.put(t, ["b#acme#0#ff"])
    >>> [c.id for c in store.candidates("acme", ["b#acme#0#ff"])] == [t.id]
    True
    >>> store.close()
    """

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Clock = utc_now,
        band_cap: int = DEFAULT_BAND_CAP,
    ) -> None:
        if band_cap < 1:
            raise ValueError(f"band_cap must be >= 1: {band_cap}")
        self._clock = clock
        self._band_cap = band_cap
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _now(self) -> float:
        return _ts(self._clock())

    @staticmethod
    def _load(data: str, hits: int, stale: int) -> Trajectory:
        return Trajectory.model_validate_json(data).model_copy(update={"hits": hits, "stale": bool(stale)})

    def put(self, trajectory: Trajectory, band_keys: Sequence[str]) -> None:
        _check_band_keys(trajectory.scope, band_keys)
        pk = trajectory_key(trajectory.scope, trajectory.id)
        created = _ts(trajectory.created_at)
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO trajectories (pk, scope, data, created_at, expires_at, hits, stale)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    pk,
                    trajectory.scope,
                    trajectory.model_dump_json(),
                    created,
                    _ts(trajectory.expires_at),
                    trajectory.hits,
                    int(trajectory.stale),
                ),
            )
            self._conn.execute("DELETE FROM bands WHERE trajectory_pk = ?", (pk,))
            for key in dict.fromkeys(band_keys):
                self._conn.execute(
                    "INSERT INTO bands (pk, trajectory_pk, created_at) VALUES (?, ?, ?)", (key, pk, created)
                )
                self._conn.execute(
                    "DELETE FROM bands WHERE pk = ? AND trajectory_pk NOT IN ("
                    " SELECT trajectory_pk FROM bands WHERE pk = ?"
                    " ORDER BY created_at DESC, trajectory_pk DESC LIMIT ?)",
                    (key, key, self._band_cap),
                )

    def get(self, scope: str, trajectory_id: str) -> Trajectory | None:
        row = self._conn.execute(
            "SELECT data, hits, stale FROM trajectories WHERE pk = ? AND expires_at > ?",
            (trajectory_key(scope, trajectory_id), self._now()),
        ).fetchone()
        return None if row is None else self._load(*row)

    def candidates(self, scope: str, band_keys: Sequence[str]) -> list[Trajectory]:
        _check_band_keys(scope, band_keys)
        keys = list(dict.fromkeys(band_keys))
        if not keys:
            return []
        placeholders = ",".join("?" * len(keys))
        rows = self._conn.execute(
            "SELECT t.data, t.hits, t.stale FROM trajectories t"
            f" WHERE t.pk IN (SELECT trajectory_pk FROM bands WHERE pk IN ({placeholders}))"
            " AND t.scope = ? AND t.stale = 0 AND t.expires_at > ?"
            " ORDER BY t.created_at DESC, t.pk DESC",
            (*keys, scope, self._now()),
        ).fetchall()
        return [self._load(*row) for row in rows]

    def mark_stale(self, scope: str, trajectory_id: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE trajectories SET stale = 1 WHERE pk = ?", (trajectory_key(scope, trajectory_id),)
            )

    def incr_hits(self, scope: str, trajectory_id: str) -> int:
        pk = trajectory_key(scope, trajectory_id)
        with self._conn:
            row = self._conn.execute(
                "UPDATE trajectories SET hits = hits + 1 WHERE pk = ? AND expires_at > ? RETURNING hits",
                (pk, self._now()),
            ).fetchone()
        return 0 if row is None else int(row[0])

    def purge_expired(self) -> int:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM trajectories WHERE expires_at <= ?", (self._now(),))
        return cursor.rowcount
