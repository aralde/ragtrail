from collections.abc import Sequence

import anyio
import pytest
from pydantic import ValidationError

from ragtrail import SQLiteStore, turn
from ragtrail.embed import (
    EMBED_BAND_OFFSET,
    EmbedConfig,
    Embedder,
    cosine,
    embed_band_keys,
    normalize_vector,
    simhash_bits,
)
from ragtrail.models import Trajectory
from ragtrail.recall import recall
from ragtrail.recorder import Recorder
from tests.corpus import Corpus

CONCEPTS = [
    {"password", "credentials", "passcode"},
    {"reset", "recover", "new", "change"},
    {"forgot", "lost", "cant", "can't"},
    {"payment", "card", "charge"},
    {"declined", "refused", "rejected"},
    {"invoice", "invoices", "bill", "receipt"},
]


class ConceptEmbedder:
    """Deterministic fake: one dimension per synonym group, plus a small constant so no vector is zero."""

    def __init__(self, name: str = "concepts-v1") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out = []
        for text in texts:
            words = {w.strip("?.,!:").lower() for w in text.split()}
            out.append([float(bool(words & group)) for group in CONCEPTS] + [0.05])
        return out


Q1 = "How do I reset my password?"
FAR = "Change of credentials: what are the steps"


def test_is_an_embedder() -> None:
    assert isinstance(ConceptEmbedder(), Embedder)


def test_vector_helpers() -> None:
    assert normalize_vector([0.0, 2.0]) == [0.0, 1.0]
    with pytest.raises(ValueError):
        normalize_vector([0.0, 0.0])
    with pytest.raises(ValueError):
        cosine([1.0], [1.0, 2.0])
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_simhash_is_deterministic_and_seeded() -> None:
    v = normalize_vector([0.3, -0.2, 0.9, 0.1])
    assert simhash_bits(v) == simhash_bits(list(v))
    assert simhash_bits(v) != simhash_bits(v, EmbedConfig(seed=1))
    keys = embed_band_keys("acme", v)
    assert len(keys) == EmbedConfig().bands
    assert {int(k.split("#")[2]) for k in keys} == set(range(EMBED_BAND_OFFSET, EMBED_BAND_OFFSET + 30))
    assert embed_band_keys("acme", v) == keys and set(keys).isdisjoint(embed_band_keys("globex", v))


def test_identical_vectors_collide_in_every_band() -> None:
    v = normalize_vector([0.5, 0.1, -0.4])
    assert embed_band_keys("s", v) == embed_band_keys("s", [x * 3 for x in v])


def test_embed_config_validation() -> None:
    with pytest.raises(ValidationError):
        EmbedConfig(bits=100, rows=16)
    with pytest.raises(ValidationError):
        EmbedConfig(hint_threshold=0.95, prefetch_threshold=0.9)
    assert EmbedConfig().collision_probability(1.0) == 1.0


def record(
    store: SQLiteStore, corpus: Corpus, query: str, cited: list[str], embedder: Embedder | None
) -> Trajectory:
    rec = Recorder(store, corpus.resolver(), "acme", query, embedder=embedder)
    rec.cite(cited)
    t = rec.commit("verified")
    assert t is not None
    return t


def test_embedding_catches_far_paraphrase() -> None:
    store, corpus, emb = SQLiteStore(":memory:"), Corpus(), ConceptEmbedder()
    t = record(store, corpus, Q1, ["n70"], emb)
    assert t.embed_model == "concepts-v1" and t.embedding is not None
    assert recall(store, corpus.resolver(), FAR, "acme").mode == "miss"
    hit = recall(store, corpus.resolver(), FAR, "acme", embedder=emb)
    assert hit.mode == "prefetch" and hit.matched_by == "embedding"
    assert [n.node_id for n in hit.nodes] == ["n70"]


def test_lexical_match_still_reported_as_lexical() -> None:
    store, corpus, emb = SQLiteStore(":memory:"), Corpus(), ConceptEmbedder()
    record(store, corpus, Q1, ["n70"], emb)
    hit = recall(store, corpus.resolver(), "how do I reset my password", "acme", embedder=emb)
    assert hit.mode == "prefetch" and hit.similarity == 1.0


def test_unrelated_query_misses_with_embeddings() -> None:
    store, corpus, emb = SQLiteStore(":memory:"), Corpus(), ConceptEmbedder()
    record(store, corpus, Q1, ["n70"], emb)
    assert recall(store, corpus.resolver(), "Why was my card refused?", "acme", embedder=emb).mode == "miss"


def test_other_model_never_compared() -> None:
    store, corpus = SQLiteStore(":memory:"), Corpus()
    record(store, corpus, Q1, ["n70"], ConceptEmbedder("concepts-v1"))
    hit = recall(store, corpus.resolver(), FAR, "acme", embedder=ConceptEmbedder("concepts-v2"))
    assert hit.mode == "miss"


def test_trails_without_embedding_still_match_lexically() -> None:
    store, corpus = SQLiteStore(":memory:"), Corpus()
    record(store, corpus, Q1, ["n70"], None)
    hit = recall(
        store,
        corpus.resolver(),
        "How can I reset my password if I forgot it",
        "acme",
        embedder=ConceptEmbedder(),
    )
    assert hit.mode == "prefetch" and hit.matched_by == "lexical"


def test_embedding_round_trips_through_store() -> None:
    store, corpus = SQLiteStore(":memory:"), Corpus()
    t = record(store, corpus, Q1, ["n70"], ConceptEmbedder())
    assert store.get("acme", t.id) == t
    assert Trajectory.model_validate_json(t.model_dump_json()) == t


def test_turn_with_embedder() -> None:
    store, corpus, emb = SQLiteStore(":memory:"), Corpus(), ConceptEmbedder()
    with turn(store, corpus.resolver(), "acme", Q1, embedder=emb) as t:
        t.cite(["n70"])
        t.accept("verified")
    with turn(store, corpus.resolver(), "acme", FAR, embedder=emb) as t2:
        assert t2.recall.matched_by == "embedding"


def test_mcp_server_with_embedder() -> None:
    pytest.importorskip("mcp")
    from mcp import Client

    from ragtrail.mcp import create_server

    async def scenario() -> None:
        server = create_server(
            SQLiteStore(":memory:"), Corpus().resolver(), "acme", embedder=ConceptEmbedder()
        )
        async with Client(server) as client:
            await client.call_tool("record", {"query": Q1, "cited": ["n70"], "outcome": "verified"})
            hit = await client.call_tool("recall", {"query": FAR})
            data = dict(hit.structured_content or {})
            assert data["mode"] == "prefetch" and data["matched_by"] == "embedding"

    anyio.run(scenario)
