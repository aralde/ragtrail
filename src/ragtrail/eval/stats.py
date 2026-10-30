"""Small, seeded statistics for paired comparisons."""

from __future__ import annotations

import math
import random
import re
import statistics
from collections import Counter
from collections.abc import Sequence

_WORD = re.compile(r"\w+")
_STOP = frozenset(
    ["a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is", "are", "be", "it", "this", "that"]
)


def token_f1(prediction: str, reference: str) -> float:
    """Bag-of-words F1 between two texts, ignoring case, punctuation and a few stop words.

    >>> round(token_f1("Go to Settings, then Payments.", "Open Settings and click Payments"), 2)
    0.5
    """
    pred = Counter(w for w in _WORD.findall(prediction.lower()) if w not in _STOP)
    ref = Counter(w for w in _WORD.findall(reference.lower()) if w not in _STOP)
    overlap = sum((pred & ref).values())
    if not overlap:
        return 0.0
    precision, recall = overlap / sum(pred.values()), overlap / sum(ref.values())
    return 2 * precision * recall / (precision + recall)


def sign_test(wins: int, losses: int) -> float:
    """Two-sided exact sign test p-value over discordant pairs.

    >>> round(sign_test(12, 3), 3), sign_test(0, 0)
    (0.035, 1.0)
    """
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(wins, losses) + 1)) / (1 << n)
    return min(1.0, 2 * tail)


def bootstrap_ci(diffs: Sequence[float], *, rounds: int = 5000, seed: int = 0) -> tuple[float, float]:
    """95% percentile bootstrap interval for the mean of paired differences (seeded).

    >>> bootstrap_ci([1.0] * 10)
    (1.0, 1.0)
    """
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(rounds))
    return means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion.

    >>> [round(x, 3) for x in wilson(8, 10)]
    [0.49, 0.943]
    """
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)
