import pytest

from ragtrail import SQLiteStore, turn
from tests.corpus import Corpus

Q = "How do I reset my password?"


@pytest.fixture
def store() -> SQLiteStore:
    return SQLiteStore(":memory:")


def test_turn_records_on_accept_and_recalls_next_time(store: SQLiteStore) -> None:
    corpus = Corpus()
    with turn(store, corpus.resolver(), "acme", Q) as t:
        assert t.recall.mode == "miss"
        t.step("search", {"q": Q}, ["n70", "n72"])
        t.cite(["n70"])
        t.accept("verified")
    assert t.trajectory is not None and t.trajectory.outcome == "verified"
    with turn(store, corpus.resolver(), "acme", Q) as t2:
        assert t2.recall.mode == "prefetch"
        assert t2.recall.trajectory_id == t.trajectory.id


def test_turn_without_outcome_stores_nothing(store: SQLiteStore) -> None:
    corpus = Corpus()
    with turn(store, corpus.resolver(), "acme", Q) as t:
        t.cite(["n70"])
    assert t.trajectory is None
    with turn(store, corpus.resolver(), "acme", Q) as t:
        assert t.recall.mode == "miss"


def test_outcome_attribute_and_default_accept(store: SQLiteStore) -> None:
    corpus = Corpus()
    with turn(store, corpus.resolver(), "acme", Q) as t:
        t.cite(["n70"])
        t.outcome = "feedback"
    assert t.trajectory is not None and t.trajectory.outcome == "feedback"
    with turn(store, corpus.resolver(), "acme", "Why was my payment declined?") as t:
        t.cite(["n90"])
        t.accept()
    assert t.trajectory is not None and t.trajectory.outcome == "accepted"


def test_exception_drops_turn_and_propagates(store: SQLiteStore) -> None:
    corpus = Corpus()
    with pytest.raises(RuntimeError, match="llm failed"), turn(store, corpus.resolver(), "acme", Q) as t:
        t.cite(["n70"])
        t.accept("verified")
        raise RuntimeError("llm failed")
    assert t.trajectory is None
    with turn(store, corpus.resolver(), "acme", Q) as t:
        assert t.recall.mode == "miss"


def test_scope_is_respected(store: SQLiteStore) -> None:
    corpus = Corpus()
    with turn(store, corpus.resolver(), "acme", Q) as t:
        t.cite(["n70"])
        t.accept()
    with turn(store, corpus.resolver(), "globex", Q) as t:
        assert t.recall.mode == "miss"
