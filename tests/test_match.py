import itertools
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from ragtrail.match import (
    DEFAULT_CONFIG,
    MatchConfig,
    band_keys,
    normalize_query,
    shingles,
    signature,
    similarity,
)
from ragtrail.normalize import normalize, stopwords_for

FIXTURES = Path(__file__).parent / "fixtures"


def sig(q: str, config: MatchConfig = DEFAULT_CONFIG) -> list[int]:
    return signature(normalize_query(q, config), config)


def groups() -> list[list[str]]:
    data = json.loads((FIXTURES / "paraphrases.json").read_text())
    return list(data["groups"])


def paraphrase_pairs() -> list[tuple[str, str]]:
    return [pair for g in groups() for pair in itertools.combinations(g, 2)]


def unrelated_pairs() -> list[tuple[str, str]]:
    return [(a, b) for g1, g2 in itertools.combinations(groups(), 2) for a in g1 for b in g2]


def test_normalize_basics() -> None:
    assert normalize("\uff21\uff43\uff43\uff45\uff53\uff53\u00a0TOKEN!!!") == "access token"
    assert normalize("¿Cómo   cancelo\tmi suscripción?") == "como cancelo mi suscripcion"
    assert normalize("Cómo", accents=True) == "cómo"
    assert normalize("rate-limit / API") == "rate limit api"
    assert normalize("v2.1 API") == "v2 1 api"
    assert normalize("") == ""
    assert normalize("?!") == ""


def test_stopwords_never_empty_the_query() -> None:
    assert normalize("the of and", stopwords=stopwords_for(["en"])) == "the of and"


def test_unknown_stopword_language() -> None:
    with pytest.raises(ValueError):
        stopwords_for(["xx"])
    with pytest.raises(ValidationError):
        MatchConfig(stopword_languages=("xx",))


def test_config_validation() -> None:
    with pytest.raises(ValidationError):
        MatchConfig(num_perm=128, bands=42, rows=3)
    with pytest.raises(ValidationError):
        MatchConfig(prefetch_threshold=0.2, hint_threshold=0.3)


def test_signature_is_deterministic_across_processes() -> None:
    code = (
        "from ragtrail.match import *; print(band_keys('s', signature(normalize_query('Reset my password'))))"
    )
    runs = {
        subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
        for _ in range(2)
    }
    assert len(runs) == 1
    assert runs.pop().strip() == str(band_keys("s", sig("Reset my password")))


def test_signature_depends_on_seed() -> None:
    other = MatchConfig(seed=1)
    assert sig("reset password") != sig("reset password", other)


def test_empty_query_cannot_be_signed() -> None:
    assert shingles("") == set()
    with pytest.raises(ValueError):
        signature("")


def test_similarity_identity_and_errors() -> None:
    s = sig("How do I reset my password?")
    assert similarity(s, s) == 1.0
    with pytest.raises(ValueError):
        similarity(s, s[:-1])
    with pytest.raises(ValueError):
        similarity([], [])


def test_band_keys_shape_and_scope() -> None:
    s = sig("reset password")
    keys = band_keys("acme", s)
    assert len(keys) == DEFAULT_CONFIG.bands
    assert [k.split("#")[2] for k in keys] == [str(i) for i in range(DEFAULT_CONFIG.bands)]
    assert set(keys).isdisjoint(band_keys("globex", s))
    with pytest.raises(ValueError):
        band_keys("acme", s[:10])


def test_paraphrases_score_above_unrelated() -> None:
    para = [similarity(sig(a), sig(b)) for a, b in paraphrase_pairs()]
    unrel = [similarity(sig(a), sig(b)) for a, b in unrelated_pairs()]
    assert min(para) > max(unrel)
    assert min(para) >= DEFAULT_CONFIG.hint_threshold > max(unrel)


def test_paraphrases_share_a_band_unrelated_rarely_do() -> None:
    def collide(a: str, b: str) -> bool:
        return bool(set(band_keys("s", sig(a))) & set(band_keys("s", sig(b))))

    assert all(collide(a, b) for a, b in paraphrase_pairs())
    unrel = unrelated_pairs()
    assert sum(collide(a, b) for a, b in unrel) / len(unrel) < 0.02


def _random_query(rng: random.Random) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzáéñü0123456789 ?¿!.,-"
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 60)))


def test_property_identical_queries_collide_in_every_band() -> None:
    rng = random.Random(7)
    checked = 0
    for _ in range(300):
        q = _random_query(rng)
        if not normalize_query(q):
            continue
        variants = [q, q.upper(), f"  {q}  ", q + "?"]
        keysets = [band_keys("acme", sig(v)) for v in variants]
        assert all(ks == keysets[0] for ks in keysets)
        checked += 1
    assert checked > 200
