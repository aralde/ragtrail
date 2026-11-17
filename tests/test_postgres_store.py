"""`PostgresStore` against a real database. Skipped unless `RAGTRAIL_PG_DSN` is set."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

import pytest

from ragtrail.models import Trajectory
from tests.test_store import T0, FakeClock, bk, traj

DSN = os.environ.get("RAGTRAIL_PG_DSN")

pytestmark = pytest.mark.skipif(DSN is None, reason="RAGTRAIL_PG_DSN not set")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(T0)


@pytest.fixture
def dsn() -> str:
    assert DSN is not None
    from ragtrail.postgres import PostgresStore

    with PostgresStore(DSN) as s:
        s._conn.execute("TRUNCATE ragtrail_trajectories CASCADE")
        s._conn.commit()
    return DSN


@pytest.fixture
def store(dsn: str, clock: FakeClock) -> Iterator[Any]:
    from ragtrail.postgres import PostgresStore

    s = PostgresStore(dsn, clock=clock, band_cap=3)
    yield s
    s.close()


def test_satisfies_protocol(store: Any) -> None:
    from ragtrail.store import TrajectoryStore

    assert isinstance(store, TrajectoryStore)


def test_put_get_round_trip(store) -> None:  # type: ignore[no-untyped-def]
    t = traj(hits=2)
    store.put(t, [bk("acme", 0)])
    assert store.get("acme", t.id) == t
    assert store.get("acme", "missing") is None


def test_candidates_newest_first_and_dedup(store) -> None:  # type: ignore[no-untyped-def]
    old = traj(created=T0)
    new = traj(created=T0 + timedelta(hours=1))
    store.put(old, [bk("acme", 0), bk("acme", 1)])
    store.put(new, [bk("acme", 0)])
    got = store.candidates("acme", [bk("acme", 0), bk("acme", 1), bk("acme", 2)])
    assert [c.id for c in got] == [new.id, old.id]


def test_put_replaces_and_reindexes(store) -> None:  # type: ignore[no-untyped-def]
    t = traj()
    store.put(t, [bk("acme", 0)])
    store.put(t, [bk("acme", 1)])
    assert store.candidates("acme", [bk("acme", 0)]) == []
    assert [c.id for c in store.candidates("acme", [bk("acme", 1)])] == [t.id]


def test_expiry_and_purge(store, clock: FakeClock) -> None:  # type: ignore[no-untyped-def]
    t = traj(ttl=timedelta(hours=1))
    store.put(t, [bk("acme", 0)])
    clock.now = T0 + timedelta(hours=2)
    assert store.get("acme", t.id) is None
    assert store.candidates("acme", [bk("acme", 0)]) == []
    assert store.incr_hits("acme", t.id) == 0
    assert store.purge_expired() == 1
    assert store.purge_expired() == 0


def test_scopes_never_mix(store) -> None:  # type: ignore[no-untyped-def]
    a = traj("acme")
    b = traj("acme-eu")
    store.put(a, [bk("acme", 0)])
    store.put(b, [bk("acme-eu", 0)])
    assert [c.id for c in store.candidates("acme", [bk("acme", 0)])] == [a.id]
    assert store.get("acme-eu", a.id) is None
    with pytest.raises(ValueError):
        store.candidates("acme", [bk("acme-eu", 0)])
    with pytest.raises(ValueError):
        store.put(a, [bk("acme-eu", 0)])


def test_mark_stale_hides_from_candidates_only(store) -> None:  # type: ignore[no-untyped-def]
    t = traj()
    store.put(t, [bk("acme", 0)])
    store.mark_stale("acme", t.id)
    store.mark_stale("acme", "missing")
    assert store.candidates("acme", [bk("acme", 0)]) == []
    got = store.get("acme", t.id)
    assert got is not None and got.stale


def test_band_bucket_is_capped_newest_first(store) -> None:  # type: ignore[no-untyped-def]
    ts = [traj(created=T0 + timedelta(minutes=i)) for i in range(5)]
    for t in ts:
        store.put(t, [bk("acme", 0)])
    got = store.candidates("acme", [bk("acme", 0)])
    assert [c.id for c in got] == [t.id for t in reversed(ts[2:])]


def test_trails_are_shared_between_connections(dsn: str, clock: FakeClock) -> None:
    from ragtrail.postgres import PostgresStore

    t = traj()
    with PostgresStore(dsn, clock=clock) as alice, PostgresStore(dsn, clock=clock) as bob:
        alice.put(t, [bk("acme", 0)])
        assert [c.id for c in bob.candidates("acme", [bk("acme", 0)])] == [t.id]
        assert bob.candidates("other", [bk("other", 0)]) == []


def test_concurrent_incr_hits_is_atomic(dsn: str, clock: FakeClock) -> None:
    from ragtrail.postgres import PostgresStore

    t: Trajectory = traj()
    with PostgresStore(dsn, clock=clock) as setup:
        setup.put(t, [bk("acme", 0)])

    def work(_: int) -> None:
        with PostgresStore(dsn, clock=clock) as s:
            for _ in range(10):
                s.incr_hits("acme", t.id)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(work, range(8)))
    with PostgresStore(dsn, clock=clock) as check:
        got = check.get("acme", t.id)
    assert got is not None and got.hits == 80


def test_rejects_bad_band_cap(dsn: str) -> None:
    from ragtrail.postgres import PostgresStore

    with pytest.raises(ValueError):
        PostgresStore(dsn, band_cap=0)


def test_incr_rejections_persists(store) -> None:  # type: ignore[no-untyped-def]
    t = traj()
    store.put(t, [])
    assert store.incr_rejections("acme", t.id) == 1
    assert store.incr_rejections("acme", t.id) == 2
    got = store.get("acme", t.id)
    assert got is not None and got.rejections == 2
    assert store.incr_rejections("acme", "missing") == 0
