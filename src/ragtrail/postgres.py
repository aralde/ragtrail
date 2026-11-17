"""`PostgresStore`: a `TrajectoryStore` on PostgreSQL, so a team shares trails (`ragtrail[postgres]`)."""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType
from typing import Any, Self

from ragtrail.keys import trajectory_key
from ragtrail.models import Trajectory
from ragtrail.store import DEFAULT_BAND_CAP, Clock, _check_band_keys, _ts, utc_now

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    raise ImportError("PostgresStore needs psycopg: pip install 'ragtrail[postgres]'") from exc

_SCHEMA_LOCK = 7_262_001

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ragtrail_trajectories (
    pk TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    hits INTEGER NOT NULL DEFAULT 0,
    stale BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ragtrail_trajectories_expires ON ragtrail_trajectories (expires_at);
CREATE TABLE IF NOT EXISTS ragtrail_bands (
    pk TEXT NOT NULL,
    trajectory_pk TEXT NOT NULL REFERENCES ragtrail_trajectories (pk) ON DELETE CASCADE,
    created_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (pk, trajectory_pk)
);
CREATE INDEX IF NOT EXISTS ragtrail_bands_trajectory ON ragtrail_bands (trajectory_pk);
"""


class PostgresStore:
    """`TrajectoryStore` backed by PostgreSQL; every process pointed at the same database shares trails.

    Scopes stay apart exactly as in the other backends: every key starts with the scope. `incr_hits`
    is a single atomic `UPDATE`, and `put` serializes per band bucket so the cap holds under concurrency.

    >>> store = PostgresStore("postgresql://user:pass@db.example.com/ragtrail")  # doctest: +SKIP
    >>> store.close()  # doctest: +SKIP
    """

    def __init__(
        self,
        dsn: str,
        *,
        clock: Clock = utc_now,
        band_cap: int = DEFAULT_BAND_CAP,
    ) -> None:
        if band_cap < 1:
            raise ValueError(f"band_cap must be >= 1: {band_cap}")
        self._clock = clock
        self._band_cap = band_cap
        self._conn: psycopg.Connection[Any] = psycopg.connect(dsn)
        with self._conn.transaction():
            self._conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK,))
            self._conn.execute(_SCHEMA)

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
    def _load(data: str, hits: int, stale: bool) -> Trajectory:
        return Trajectory.model_validate_json(data).model_copy(update={"hits": hits, "stale": stale})

    def put(self, trajectory: Trajectory, band_keys: Sequence[str]) -> None:
        _check_band_keys(trajectory.scope, band_keys)
        pk = trajectory_key(trajectory.scope, trajectory.id)
        created = _ts(trajectory.created_at)
        keys = sorted(dict.fromkeys(band_keys))
        with self._conn.transaction():
            for key in keys:
                self._conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (key,))
            self._conn.execute(
                "INSERT INTO ragtrail_trajectories (pk, scope, data, created_at, expires_at, hits, stale)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (pk) DO UPDATE SET scope = EXCLUDED.scope, data = EXCLUDED.data,"
                " created_at = EXCLUDED.created_at, expires_at = EXCLUDED.expires_at,"
                " hits = EXCLUDED.hits, stale = EXCLUDED.stale",
                (
                    pk,
                    trajectory.scope,
                    trajectory.model_dump_json(),
                    created,
                    _ts(trajectory.expires_at),
                    trajectory.hits,
                    trajectory.stale,
                ),
            )
            self._conn.execute("DELETE FROM ragtrail_bands WHERE trajectory_pk = %s", (pk,))
            for key in keys:
                self._conn.execute(
                    "INSERT INTO ragtrail_bands (pk, trajectory_pk, created_at) VALUES (%s, %s, %s)",
                    (key, pk, created),
                )
                self._conn.execute(
                    "DELETE FROM ragtrail_bands WHERE pk = %s AND trajectory_pk NOT IN ("
                    " SELECT trajectory_pk FROM ragtrail_bands WHERE pk = %s"
                    " ORDER BY created_at DESC, trajectory_pk DESC LIMIT %s)",
                    (key, key, self._band_cap),
                )

    def get(self, scope: str, trajectory_id: str) -> Trajectory | None:
        row = self._conn.execute(
            "SELECT data, hits, stale FROM ragtrail_trajectories WHERE pk = %s AND expires_at > %s",
            (trajectory_key(scope, trajectory_id), self._now()),
        ).fetchone()
        return None if row is None else self._load(*row)

    def candidates(self, scope: str, band_keys: Sequence[str]) -> list[Trajectory]:
        _check_band_keys(scope, band_keys)
        keys = list(dict.fromkeys(band_keys))
        if not keys:
            return []
        rows = self._conn.execute(
            "SELECT t.data, t.hits, t.stale FROM ragtrail_trajectories t"
            " WHERE t.pk IN (SELECT trajectory_pk FROM ragtrail_bands WHERE pk = ANY(%s))"
            " AND t.scope = %s AND NOT t.stale AND t.expires_at > %s"
            " ORDER BY t.created_at DESC, t.pk DESC",
            (keys, scope, self._now()),
        ).fetchall()
        return [self._load(*row) for row in rows]

    def mark_stale(self, scope: str, trajectory_id: str) -> None:
        self._conn.execute(
            "UPDATE ragtrail_trajectories SET stale = TRUE WHERE pk = %s",
            (trajectory_key(scope, trajectory_id),),
        )
        self._conn.commit()

    def incr_hits(self, scope: str, trajectory_id: str) -> int:
        row = self._conn.execute(
            "UPDATE ragtrail_trajectories SET hits = hits + 1 WHERE pk = %s AND expires_at > %s"
            " RETURNING hits",
            (trajectory_key(scope, trajectory_id), self._now()),
        ).fetchone()
        self._conn.commit()
        return 0 if row is None else int(row[0])

    def purge_expired(self) -> int:
        cursor = self._conn.execute(
            "DELETE FROM ragtrail_trajectories WHERE expires_at <= %s", (self._now(),)
        )
        self._conn.commit()
        return cursor.rowcount
