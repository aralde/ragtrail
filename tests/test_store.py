"""Behaviour every `TrajectoryStore` backend must satisfy. Add new backends to the `store` fixture."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ragtrail.keys import band_key
from ragtrail.models import NodeRef, Trajectory
from ragtrail.store import SQLiteStore, TrajectoryStore

T0 = datetime(2026, 1, 1, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(T0)


@pytest.fixture(params=["sqlite-memory", "sqlite-file"])
def store(request: pytest.FixtureRequest, clock: FakeClock, tmp_path: Path) -> Iterator[TrajectoryStore]:
    path = ":memory:" if request.param == "sqlite-memory" else tmp_path / "trails.db"
    s = SQLiteStore(path, clock=clock, band_cap=3)
    yield s
    s.close()


def traj(
    scope: str = "acme", *, created: datetime = T0, ttl: timedelta = timedelta(days=1), **kw: object
) -> Trajectory:
    fields: dict[str, object] = {
        "scope": scope,
        "query": "q",
        "query_norm": "q",
        "signature": [1, 2],
        "useful": [NodeRef(node_id="n1", content_hash="h1")],
        "outcome": "verified",
        "created_at": created,
        "expires_at": created + ttl,
    }
    fields.update(kw)
    return Trajectory.model_validate(fields)


def bk(scope: str, idx: int, h: str = "ff") -> str:
    return band_key(scope, idx, h)


def test_sqlite_store_satisfies_protocol(store: TrajectoryStore) -> None:
    assert isinstance(store, TrajectoryStore)


def test_put_get_round_trip(store: TrajectoryStore) -> None:
    t = traj()
    store.put(t, [bk("acme", 0)])
    assert store.get("acme", t.id) == t


def test_get_missing_returns_none(store: TrajectoryStore) -> None:
    assert store.get("acme", "nope") is None


def test_candidates_union_dedup_newest_first(store: TrajectoryStore) -> None:
    old = traj(created=T0 - timedelta(hours=2))
    new = traj(created=T0 - timedelta(hours=1))
    store.put(old, [bk("acme", 0), bk("acme", 1)])
    store.put(new, [bk("acme", 1), bk("acme", 2)])
    got = store.candidates("acme", [bk("acme", 0), bk("acme", 1), bk("acme", 2)])
    assert [c.id for c in got] == [new.id, old.id]
    assert store.candidates("acme", [bk("acme", 5)]) == []
    assert store.candidates("acme", []) == []


def test_put_replaces_and_reindexes(store: TrajectoryStore) -> None:
    t = traj()
    store.put(t, [bk("acme", 0)])
    updated = t.model_copy(update={"query": "q2"})
    store.put(updated, [bk("acme", 1)])
    assert store.candidates("acme", [bk("acme", 0)]) == []
    assert [c.query for c in store.candidates("acme", [bk("acme", 1)])] == ["q2"]


def test_expired_items_never_returned(store: TrajectoryStore, clock: FakeClock) -> None:
    t = traj(ttl=timedelta(hours=1))
    store.put(t, [bk("acme", 0)])
    clock.now = T0 + timedelta(hours=1)
    assert store.get("acme", t.id) is None
    assert store.candidates("acme", [bk("acme", 0)]) == []
    assert store.incr_hits("acme", t.id) == 0


def test_purge_expired(store: TrajectoryStore, clock: FakeClock) -> None:
    short = traj(ttl=timedelta(hours=1))
    long = traj(ttl=timedelta(days=2))
    store.put(short, [bk("acme", 0)])
    store.put(long, [bk("acme", 0)])
    clock.now = T0 + timedelta(hours=2)
    assert store.purge_expired() == 1
    assert store.purge_expired() == 0
    clock.now = T0
    assert store.get("acme", short.id) is None
    assert [c.id for c in store.candidates("acme", [bk("acme", 0)])] == [long.id]


def test_scopes_never_mix(store: TrajectoryStore) -> None:
    a = traj("acme")
    b = traj("globex")
    store.put(a, [bk("acme", 0)])
    store.put(b, [bk("globex", 0)])
    assert store.get("globex", a.id) is None
    assert [c.id for c in store.candidates("acme", [bk("acme", 0)])] == [a.id]
    assert [c.id for c in store.candidates("globex", [bk("globex", 0)])] == [b.id]
    with pytest.raises(ValueError):
        store.candidates("acme", [bk("globex", 0)])
    store.mark_stale("globex", a.id)
    assert store.incr_hits("globex", a.id) == 0
    assert store.get("acme", a.id) == a


def test_scope_prefix_is_not_a_scope(store: TrajectoryStore) -> None:
    a = traj("acme")
    store.put(a, [bk("acme", 0)])
    with pytest.raises(ValueError):
        store.candidates("acme-eu", [bk("acme", 0)])
    assert store.candidates("acme-eu", [bk("acme-eu", 0)]) == []


def test_put_rejects_band_keys_of_other_scope(store: TrajectoryStore) -> None:
    with pytest.raises(ValueError):
        store.put(traj("acme"), [bk("globex", 0)])
    with pytest.raises(ValueError):
        store.put(traj("acme"), ["t#acme#x"])


def test_mark_stale_hides_from_candidates_only(store: TrajectoryStore) -> None:
    t = traj()
    store.put(t, [bk("acme", 0)])
    store.mark_stale("acme", t.id)
    assert store.candidates("acme", [bk("acme", 0)]) == []
    got = store.get("acme", t.id)
    assert got is not None and got.stale
    store.mark_stale("acme", "missing")


def test_incr_hits(store: TrajectoryStore) -> None:
    t = traj()
    store.put(t, [bk("acme", 0)])
    assert store.incr_hits("acme", t.id) == 1
    assert store.incr_hits("acme", t.id) == 2
    got = store.get("acme", t.id)
    assert got is not None and got.hits == 2
    assert store.incr_hits("acme", "missing") == 0


def test_band_bucket_is_capped_newest_first(store: TrajectoryStore) -> None:
    ts = [traj(created=T0 - timedelta(minutes=10 - i)) for i in range(5)]
    for t in ts:
        store.put(t, [bk("acme", 0), bk("acme", 1, "aa")])
    got = store.candidates("acme", [bk("acme", 0)])
    assert [c.id for c in got] == [t.id for t in reversed(ts[-3:])]


def test_sqlite_persists_across_connections(tmp_path: Path, clock: FakeClock) -> None:
    path = tmp_path / "trails.db"
    t = traj()
    with SQLiteStore(path, clock=clock) as s:
        s.put(t, [bk("acme", 0)])
        s.incr_hits("acme", t.id)
    with SQLiteStore(path, clock=clock) as s:
        got = s.get("acme", t.id)
    assert got is not None and got.hits == 1


def test_sqlite_rejects_bad_band_cap() -> None:
    with pytest.raises(ValueError):
        SQLiteStore(":memory:", band_cap=0)
