from datetime import UTC, datetime, timedelta

import pytest

from ragtrail.recall import recall, render
from ragtrail.recorder import Recorder
from ragtrail.store import SQLiteStore
from tests.corpus import Corpus, ScriptedAgent

Q1 = "How do I reset my password?"
Q2 = "How can I reset my password if I forgot it"
Q3 = "password reset"


@pytest.fixture
def store() -> SQLiteStore:
    return SQLiteStore(":memory:")


@pytest.fixture
def corpus() -> Corpus:
    return Corpus()


def record(store: SQLiteStore, corpus: Corpus, query: str, cited: list[str], scope: str = "acme") -> None:
    rec = Recorder(store, corpus.resolver(), scope, query)
    rec.step("search", {"q": query}, corpus.search(query))
    rec.cite(cited)
    assert rec.commit("verified") is not None


def test_scripted_agent_acceptance(store: SQLiteStore, corpus: Corpus) -> None:
    agent = ScriptedAgent(corpus, store)
    assert agent.ask(Q1, ["n70", "n72"]) == "miss"
    cold_calls = agent.tool_calls

    agent.tool_calls = 0
    assert 0.5 <= recall(store, corpus.resolver(), Q2, "acme").similarity < 1.0
    assert agent.ask(Q2, ["n70", "n72"]) == "prefetch"
    assert agent.tool_calls < cold_calls

    corpus.edit("n72", "Password reset emails now expire after 2 hours.")
    hit = recall(store, corpus.resolver(), Q2, "acme")
    assert hit.mode == "hint"
    assert [n.node_id for n in hit.nodes] == ["n70"]
    assert hit.stale == ["n72"]
    assert "Account › Password [n70]" in hit.rendered
    assert "Changed since: Account › Email [n72] (skipped)" in hit.rendered

    corpus.edit("n70", "Passwords are now reset from the mobile app only.")
    assert recall(store, corpus.resolver(), Q2, "acme").mode == "miss"


def test_total_staleness_marks_trajectory_stale(store: SQLiteStore, corpus: Corpus) -> None:
    rec = Recorder(store, corpus.resolver(), "acme", Q1)
    rec.cite(["n70"])
    t = rec.commit("verified")
    assert t is not None
    corpus.edit("n70", "changed")
    assert recall(store, corpus.resolver(), Q1, "acme").mode == "miss"
    got = store.get("acme", t.id)
    assert got is not None and got.stale
    corpus.edit("n70", "changed again")
    record(store, corpus, Q1, ["n70"])
    assert recall(store, corpus.resolver(), Q1, "acme").mode == "prefetch"


def test_deleted_node_counts_as_changed(store: SQLiteStore, corpus: Corpus) -> None:
    record(store, corpus, Q1, ["n70", "n72"])
    del corpus.texts["n72"]
    hit = recall(store, corpus.resolver(), Q1, "acme")
    assert hit.mode == "hint" and hit.stale == ["n72"]


def test_prefetch_includes_node_text_with_breadcrumbs(store: SQLiteStore, corpus: Corpus) -> None:
    record(store, corpus, Q1, ["n70"])
    hit = recall(store, corpus.resolver(), Q2, "acme")
    assert hit.mode == "prefetch"
    assert hit.rendered.startswith("ragtrail: similar question solved before (similarity ")
    assert "--- Account › Password [n70]\n" + corpus.texts["n70"] in hit.rendered
    assert hit.trajectory_id is not None
    got = store.get("acme", hit.trajectory_id)
    assert got is not None and got.hits == 1


def test_mid_similarity_gives_hint_even_when_valid(store: SQLiteStore, corpus: Corpus) -> None:
    record(store, corpus, Q1, ["n70"])
    hit = recall(store, corpus.resolver(), Q3, "acme")
    assert 0.25 <= hit.similarity < 0.5
    assert hit.mode == "hint" and hit.stale == []
    assert hit.rendered.endswith('Start with read("n70") before searching.')
    assert corpus.reads == 0


def test_unrelated_query_misses(store: SQLiteStore, corpus: Corpus) -> None:
    record(store, corpus, Q1, ["n70"])
    assert recall(store, corpus.resolver(), "Why was my payment declined?", "acme").mode == "miss"
    assert recall(store, corpus.resolver(), "?!", "acme").mode == "miss"


def test_scopes_never_mix(store: SQLiteStore, corpus: Corpus) -> None:
    record(store, corpus, Q1, ["n70"], scope="acme")
    assert recall(store, corpus.resolver(), Q1, "globex").mode == "miss"


def test_best_candidate_wins_and_stale_ones_are_skipped(store: SQLiteStore, corpus: Corpus) -> None:
    record(store, corpus, "How do I refresh an expired access token?", ["n35"])
    record(store, corpus, "Refresh expired access token", ["n33"])
    hit = recall(store, corpus.resolver(), "Refresh expired access token", "acme")
    assert hit.similarity == 1.0 and [n.node_id for n in hit.nodes] == ["n33"]
    corpus.edit("n33", "changed")
    hit = recall(store, corpus.resolver(), "Refresh expired access token", "acme")
    assert hit.mode != "miss" and [n.node_id for n in hit.nodes] == ["n35"]


def test_prefetch_respects_budget_and_collapses(store: SQLiteStore, corpus: Corpus) -> None:
    corpus.edit("n72", "x " * 400)
    record(store, corpus, Q1, ["n70", "n72"])
    hit = recall(store, corpus.resolver(), Q1, "acme", budget_tokens=120)
    assert hit.mode == "prefetch"
    assert len(hit.rendered) / 4 <= 120
    assert "Not prefetched (budget):\n    Account › Email [n72]" in hit.rendered
    assert "x x x" not in hit.rendered


def test_prefetch_with_nothing_fitting_falls_back_to_hint(store: SQLiteStore, corpus: Corpus) -> None:
    corpus.edit("n70", "y " * 400)
    record(store, corpus, Q1, ["n70"])
    hit = recall(store, corpus.resolver(), Q1, "acme", budget_tokens=60)
    assert hit.mode == "hint"
    assert "y y y" not in hit.rendered


def test_hint_list_collapses_under_budget(store: SQLiteStore, corpus: Corpus) -> None:
    nodes = list(corpus.texts)
    record(store, corpus, Q1, nodes)
    corpus.edit("n31", "changed")
    hit = recall(store, corpus.resolver(), Q1, "acme", budget_tokens=70)
    assert hit.mode == "hint"
    assert "more nodes)" in hit.rendered
    assert len(hit.rendered) / 4 <= 70


def test_render_without_labels_uses_ids(corpus: Corpus) -> None:
    from ragtrail.models import NodeRef
    from ragtrail.resolver import GenericResolver

    r = GenericResolver(lambda i: "h", lambda i, n: "text")
    mode, text = render("hint", 0.4, [NodeRef(node_id="c9", content_hash="h")], [], r, 500)
    assert mode == "hint" and "    [c9]" in text


def test_bad_budget(store: SQLiteStore, corpus: Corpus) -> None:
    with pytest.raises(ValueError):
        recall(store, corpus.resolver(), Q1, "acme", budget_tokens=0)


class TestAdmission:
    def test_no_outcome_stores_nothing(self, store: SQLiteStore, corpus: Corpus) -> None:
        rec = Recorder(store, corpus.resolver(), "acme", Q1)
        rec.cite(["n70"])
        assert rec.commit(None) is None
        assert recall(store, corpus.resolver(), Q1, "acme").mode == "miss"

    def test_no_citations_stores_nothing(self, store: SQLiteStore, corpus: Corpus) -> None:
        rec = Recorder(store, corpus.resolver(), "acme", Q1)
        rec.step("search", {"q": Q1}, ["n70"])
        assert rec.commit("accepted") is None

    def test_only_unknown_citations_stores_nothing(self, store: SQLiteStore, corpus: Corpus) -> None:
        rec = Recorder(store, corpus.resolver(), "acme", Q1)
        rec.cite(["nope"])
        assert rec.commit("verified") is None

    def test_empty_query_stores_nothing(self, store: SQLiteStore, corpus: Corpus) -> None:
        rec = Recorder(store, corpus.resolver(), "acme", "?!")
        rec.cite(["n70"])
        assert rec.commit("verified") is None

    def test_commit_once(self, store: SQLiteStore, corpus: Corpus) -> None:
        rec = Recorder(store, corpus.resolver(), "acme", Q1)
        rec.cite(["n70", "n70", "n72"])
        t = rec.commit("feedback")
        assert t is not None and [n.node_id for n in t.useful] == ["n70", "n72"]
        with pytest.raises(RuntimeError):
            rec.commit("feedback")
        with pytest.raises(RuntimeError):
            rec.step("read")

    def test_ttl_and_clock(self, store: SQLiteStore, corpus: Corpus) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        rec = Recorder(store, corpus.resolver(), "acme", Q1, ttl=timedelta(hours=2), clock=lambda: now)
        rec.cite(["n70"])
        t = rec.commit("accepted")
        assert t is not None and t.expires_at == now + timedelta(hours=2)
        with pytest.raises(ValueError):
            Recorder(store, corpus.resolver(), "acme", Q1, ttl=timedelta(0))

    def test_answers_are_never_stored(self, store: SQLiteStore, corpus: Corpus) -> None:
        rec = Recorder(store, corpus.resolver(), "acme", Q1)
        rec.cite(["n70"])
        t = rec.commit("verified")
        assert t is not None
        assert corpus.texts["n70"] not in t.model_dump_json()
