"""MinHash signatures with LSH banding. Pure stdlib and deterministic: same query, same keys."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ragtrail.keys import band_key
from ragtrail.normalize import normalize, stopwords_for

_MERSENNE_61 = (1 << 61) - 1


def _hash64(text: str) -> int:
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


class MatchConfig(BaseModel):
    """Every matcher tunable in one place. Changing any of them changes the band keys: re-record after.

    More bands of fewer rows → more candidates (higher recall, more reads); fewer, wider bands → only
    near-duplicates collide. With `bands` b and `rows` r, two queries with Jaccard s share at least one band
    with probability 1 - (1 - s**r)**b.

    >>> MatchConfig().num_perm
    126
    >>> round(MatchConfig().collision_probability(0.5), 3)
    0.996
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    num_perm: int = Field(default=126, ge=1)
    bands: int = Field(default=42, ge=1)
    rows: int = Field(default=3, ge=1)
    seed: int = 20261029
    word_ngram: int = Field(default=2, ge=1)
    char_ngram: int = Field(default=4, ge=1)
    stopword_languages: tuple[str, ...] = ("en", "es")
    keep_accents: bool = False
    prefetch_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    hint_threshold: float = Field(default=0.25, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check(self) -> MatchConfig:
        if self.bands * self.rows != self.num_perm:
            raise ValueError(
                f"bands * rows must equal num_perm ({self.bands} * {self.rows} != {self.num_perm})"
            )
        if self.hint_threshold > self.prefetch_threshold:
            raise ValueError("hint_threshold must be <= prefetch_threshold")
        stopwords_for(self.stopword_languages)
        return self

    @cached_property
    def _permutations(self) -> tuple[tuple[int, int], ...]:
        rng = random.Random(self.seed)
        return tuple(
            (rng.randrange(1, _MERSENNE_61), rng.randrange(0, _MERSENNE_61)) for _ in range(self.num_perm)
        )

    @cached_property
    def _stopwords(self) -> frozenset[str]:
        return stopwords_for(self.stopword_languages)

    def collision_probability(self, jaccard: float) -> float:
        """Probability that two queries with this Jaccard similarity share at least one band.

        >>> MatchConfig().collision_probability(1.0)
        1.0
        """
        return 1.0 - (1.0 - jaccard**self.rows) ** self.bands


DEFAULT_CONFIG = MatchConfig()


def normalize_query(query: str, config: MatchConfig = DEFAULT_CONFIG) -> str:
    """Normalize `query` with the config's stopwords and accent handling.

    >>> normalize_query("How do I refresh the token?")
    'how refresh token'
    """
    return normalize(query, stopwords=config._stopwords, accents=config.keep_accents)


def shingles(query_norm: str, config: MatchConfig = DEFAULT_CONFIG) -> set[str]:
    """Word n-grams (`w:`) and char n-grams (`c:`) of an already normalized query.

    Texts shorter than an n-gram contribute themselves as a single shingle.

    >>> sorted(shingles("reset pw"))
    ['c:eset', 'c:et p', 'c:rese', 'c:set ', 'c:t pw', 'w:reset pw']
    >>> shingles("")
    set()
    """
    if not query_norm:
        return set()
    words = query_norm.split()
    n, k = config.word_ngram, config.char_ngram
    out = {"w:" + " ".join(words[i : i + n]) for i in range(max(1, len(words) - n + 1))}
    out |= {"c:" + query_norm[i : i + k] for i in range(max(1, len(query_norm) - k + 1))}
    return out


def signature(query_norm: str, config: MatchConfig = DEFAULT_CONFIG) -> list[int]:
    """MinHash signature (`num_perm` ints below 2**61) of a normalized query.

    Raises `ValueError` for an empty query: there is nothing to match on.

    >>> sig = signature("how refresh token")
    >>> len(sig), sig == signature("how refresh token")
    (126, True)
    """
    items = shingles(query_norm, config)
    if not items:
        raise ValueError("cannot sign an empty query")
    hashed = [_hash64(s) % _MERSENNE_61 for s in items]
    return [min((a * x + b) % _MERSENNE_61 for x in hashed) for a, b in config._permutations]


def similarity(sig_a: Sequence[int], sig_b: Sequence[int]) -> float:
    """Estimated Jaccard similarity: the fraction of positions where two signatures agree.

    >>> similarity([1, 2, 3, 4], [1, 2, 0, 0])
    0.5
    """
    if len(sig_a) != len(sig_b):
        raise ValueError(f"signature lengths differ: {len(sig_a)} != {len(sig_b)}")
    if not sig_a:
        raise ValueError("empty signatures")
    return sum(a == b for a, b in zip(sig_a, sig_b, strict=True)) / len(sig_a)


def band_keys(scope: str, sig: Sequence[int], config: MatchConfig = DEFAULT_CONFIG) -> list[str]:
    """One store key per LSH band: `b#{scope}#{band_idx}#{band_hash}`.

    >>> keys = band_keys("acme", signature("how refresh token"))
    >>> len(keys), keys[0].startswith("b#acme#0#")
    (42, True)
    """
    if len(sig) != config.num_perm:
        raise ValueError(f"signature has {len(sig)} values, config expects {config.num_perm}")
    keys = []
    for i in range(config.bands):
        rows = sig[i * config.rows : (i + 1) * config.rows]
        digest = hashlib.blake2b(",".join(map(str, rows)).encode(), digest_size=8).hexdigest()
        keys.append(band_key(scope, i, digest))
    return keys
