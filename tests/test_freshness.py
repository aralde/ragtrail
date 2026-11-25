import pytest

from ragtrail.freshness import FreshnessCheck
from ragtrail.middleware import turn
from ragtrail.recall import recall
from ragtrail.recorder import Recorder
from ragtrail.resolver import GenericResolver, text_hash
from ragtrail.store import SQLiteStore

Q = "How do I rotate a token?"


class Docs:
    def __init__(self) -> None:
        self.texts = {"old": "Rotate a token from the settings page.", "misc": "Billing and invoices."}
        self.searches = 0

    def resolver(self) -> GenericResolver:
        return GenericResolver(
            lambda i: text_hash(self.texts[i]) if i in self.texts else None, lambda i, n: self.texts[i]
        )

    def search(self, query: str) -> list[str]:
        self.searches += 1
        words = set(query.lower().strip("?").split())
        scored = [(sum(w in t.lower() for w in words), k) for k, t in self.texts.items()]
        return [k for s, k in sorted(scored, reverse=True) if s > 0]


@pytest.fixture
def docs() -> Docs:
    return Docs()


@pytest.fixture
def store(docs: Docs) -> SQLiteStore:
    s = SQLiteStore(":memory:")
    rec = Recorder(s, docs.resolver(), "acme", Q)
    rec.step("search", {"q": Q}, docs.search(Q))
    rec.cite(["old"])
    assert rec.commit("verified") is not None
    return s


def test_newer_page_outranking_cited_one_marks_trail_stale(store: SQLiteStore, docs: Docs) -> None:
    docs.texts["new"] = "How do I rotate a token: rotate an API token with the CLI, step by step."
    check = FreshnessCheck(search=docs.search, sample_rate=1.0)

    hit = recall(store, docs.resolver(), Q, "acme", freshness=check)
    assert hit.mode == "miss"
    assert docs.searches == 2
    assert recall(store, docs.resolver(), Q, "acme").mode == "miss"


def test_cited_page_still_on_top_keeps_trail(store: SQLiteStore, docs: Docs) -> None:
    docs.texts["new"] = "Tokens."
    check = FreshnessCheck(search=docs.search, sample_rate=1.0)
    assert recall(store, docs.resolver(), Q, "acme", freshness=check).mode == "prefetch"
    assert recall(store, docs.resolver(), Q, "acme").mode == "prefetch"


def test_unsampled_recall_does_not_search(store: SQLiteStore, docs: Docs) -> None:
    docs.texts["new"] = "How do I rotate a token: rotate an API token with the CLI, step by step."
    check = FreshnessCheck(search=docs.search, sample_rate=0.0)
    assert recall(store, docs.resolver(), Q, "acme", freshness=check).mode == "prefetch"
    assert docs.searches == 1


def test_sample_rate_is_honoured(store: SQLiteStore, docs: Docs) -> None:
    draws = iter([0.9, 0.1, 0.5, 0.2])
    check = FreshnessCheck(search=docs.search, sample_rate=0.3, draw=lambda: next(draws))
    for _ in range(4):
        assert recall(store, docs.resolver(), Q, "acme", freshness=check).mode == "prefetch"
    assert docs.searches == 1 + 2


def test_miss_does_not_draw_or_search(store: SQLiteStore, docs: Docs) -> None:
    check = FreshnessCheck(search=docs.search, sample_rate=1.0)
    assert recall(store, docs.resolver(), "billing invoices", "acme", freshness=check).mode == "miss"
    assert docs.searches == 1


def test_turn_passes_freshness_check(store: SQLiteStore, docs: Docs) -> None:
    docs.texts["new"] = "How do I rotate a token: rotate an API token with the CLI, step by step."
    check = FreshnessCheck(search=docs.search, sample_rate=1.0)
    with turn(store, docs.resolver(), "acme", Q, freshness=check) as t:
        assert t.recall.mode == "miss"


@pytest.mark.parametrize("rate", [-0.1, 1.5])
def test_sample_rate_must_be_a_fraction(rate: float) -> None:
    with pytest.raises(ValueError, match="sample_rate"):
        FreshnessCheck(search=lambda q: [], sample_rate=rate)
