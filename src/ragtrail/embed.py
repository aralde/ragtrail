"""Optional embedding matcher: SimHash LSH over query embeddings, stored under the same band-key layout.

Lexical MinHash catches near-duplicates; embeddings catch paraphrases that share few words. Band keys use
indices from `EMBED_BAND_OFFSET` up, so both matchers live side by side in any `TrajectoryStore`.
Pure stdlib except the embedding model itself (`FastEmbedder`, in the `ragtrail[embed]` extra).
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ragtrail.keys import band_key

EMBED_BAND_OFFSET = 100
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


@runtime_checkable
class Embedder(Protocol):
    """Turns texts into vectors. `name` identifies the model: vectors from different models never compare."""

    @property
    def name(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text."""
        ...


class EmbedConfig(BaseModel):
    """Embedding matcher tunables. Changing `bits`, `rows` or `seed` changes the band keys: re-record after.

    Two queries at cosine c agree on one hyperplane bit with probability 1 - arccos(c)/π, so with b bands
    of r bits they share a band with probability 1 - (1 - p**r)**b.

    >>> round(EmbedConfig().collision_probability(0.88), 2)
    0.86
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bits: int = Field(default=480, ge=1)
    rows: int = Field(default=16, ge=1)
    seed: int = 20261030
    hint_threshold: float = Field(default=0.88, ge=-1.0, le=1.0)
    prefetch_threshold: float = Field(default=0.92, ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def _check(self) -> EmbedConfig:
        if self.bits % self.rows:
            raise ValueError(f"bits ({self.bits}) must be a multiple of rows ({self.rows})")
        if self.hint_threshold > self.prefetch_threshold:
            raise ValueError("hint_threshold must be <= prefetch_threshold")
        return self

    @property
    def bands(self) -> int:
        return self.bits // self.rows

    def collision_probability(self, cosine: float) -> float:
        """Probability that two vectors at this cosine share at least one band."""
        p = 1.0 - math.acos(max(-1.0, min(1.0, cosine))) / math.pi
        return 1.0 - (1.0 - p**self.rows) ** self.bands


DEFAULT_EMBED_CONFIG = EmbedConfig()


def normalize_vector(vector: Sequence[float], digits: int = 5) -> list[float]:
    """Unit-length copy, rounded to keep stored trails small.

    >>> normalize_vector([3.0, 4.0])
    [0.6, 0.8]
    """
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        raise ValueError("cannot normalize a zero vector")
    return [round(x / norm, digits) for x in vector]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two vectors.

    >>> cosine([1.0, 0.0], [0.0, 1.0]), round(cosine([1.0, 1.0], [2.0, 2.0]), 6)
    (0.0, 1.0)
    """
    if len(a) != len(b):
        raise ValueError(f"vector lengths differ: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


@lru_cache(maxsize=8)
def _planes(bits: int, dim: int, seed: int) -> tuple[tuple[float, ...], ...]:
    rng = random.Random(seed)
    return tuple(tuple(rng.gauss(0.0, 1.0) for _ in range(dim)) for _ in range(bits))


def simhash_bits(vector: Sequence[float], config: EmbedConfig = DEFAULT_EMBED_CONFIG) -> list[bool]:
    """Sign of the vector's projection on `bits` seeded random hyperplanes.

    >>> len(simhash_bits([0.1, 0.2, 0.3]))
    480
    """
    planes = _planes(config.bits, len(vector), config.seed)
    return [sum(p * v for p, v in zip(plane, vector, strict=True)) > 0 for plane in planes]


def embed_band_keys(
    scope: str, vector: Sequence[float], config: EmbedConfig = DEFAULT_EMBED_CONFIG
) -> list[str]:
    """One store key per SimHash band: `b#{scope}#{100 + band}#{hash}`.

    >>> keys = embed_band_keys("acme", [0.1, 0.2, 0.3])
    >>> len(keys), keys[0].startswith("b#acme#100#")
    (30, True)
    """
    bits = simhash_bits(vector, config)
    keys = []
    for b in range(config.bands):
        chunk = "".join("1" if x else "0" for x in bits[b * config.rows : (b + 1) * config.rows])
        digest = hashlib.blake2b(chunk.encode(), digest_size=8).hexdigest()
        keys.append(band_key(scope, EMBED_BAND_OFFSET + b, digest))
    return keys


class FastEmbedder:
    """`Embedder` backed by fastembed (ONNX, CPU). Needs `ragtrail[embed]`; downloads the model once.

    >>> FastEmbedder.__name__
    'FastEmbedder'
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - depends on the extra
            raise ImportError("FastEmbedder needs the extra: pip install 'ragtrail[embed]'") from exc
        self._name = model
        self._model: Any = TextEmbedding(model)

    @property
    def name(self) -> str:
        return self._name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(x) for x in v] for v in self._model.embed(list(texts))]
