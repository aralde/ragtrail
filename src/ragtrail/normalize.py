"""Query normalization: the canonical text that signatures are computed from."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

_EN = """
a an the and or but if of to in on at by for with from into onto about as is are was were be been
being am do does did doing have has had having i me my we our us you your he him his she her it its
they them their this that these those there here can could should would will shall may might must so
than then too very just also any some all each please
"""
_ES = """
el la los las un una unos unas y o u e pero si de del al a en con por para sin sobre entre hasta
desde es son era eran ser fue fueron estar esta estan este esto estos estas ese esa esos esas eso
aquel aquella hay he ha han hemos haber yo me mi mis tu tus te su sus se le les lo nos nuestro
nuestra vos usted ustedes ellos ellas que muy mas ya tambien puedo puede pueden podria hacer favor
"""

STOPWORDS: dict[str, frozenset[str]] = {"en": frozenset(_EN.split()), "es": frozenset(_ES.split())}
"""Small built-in stopword lists, accent-free. Question words (how/why/cómo…) are kept: they change intent."""


def strip_accents(text: str) -> str:
    """Remove combining diacritics.

    >>> strip_accents("¿Cómo añado un artículo?")
    '¿Como anado un articulo?'
    """
    decomposed = unicodedata.normalize("NFD", text)
    return unicodedata.normalize("NFC", "".join(c for c in decomposed if not unicodedata.combining(c)))


def stopwords_for(languages: Iterable[str]) -> frozenset[str]:
    """Union of the built-in stopword lists for `languages` (accent-free, like normalized text).

    >>> "the" in stopwords_for(["en"]), "el" in stopwords_for(["en"])
    (True, False)
    """
    words: set[str] = set()
    for lang in languages:
        try:
            words |= STOPWORDS[lang]
        except KeyError:
            raise ValueError(f"no stopword list for {lang!r}; available: {sorted(STOPWORDS)}") from None
    return frozenset(words)


def normalize(query: str, *, stopwords: Iterable[str] = (), accents: bool = False) -> str:
    """Canonical form of a query: NFKC, lowercase, punctuation and symbols to spaces, whitespace collapsed.

    `stopwords` are dropped after normalization, unless that would leave nothing; `accents=False`
    (default) strips diacritics so "cómo" and "como" match.

    >>> normalize("  How do I REFRESH an access-token?? ")
    'how do i refresh an access token'
    >>> normalize("How do I refresh an access token?", stopwords=stopwords_for(["en"]))
    'how refresh access token'
    >>> normalize("¿Cómo renuevo el token?")
    'como renuevo el token'
    """
    text = unicodedata.normalize("NFKC", query).lower()
    if not accents:
        text = strip_accents(text)
    text = "".join(" " if unicodedata.category(c)[0] in "PSZC" else c for c in text)
    words = text.split()
    if stopwords:
        drop = frozenset(stopwords)
        words = [w for w in words if w not in drop] or words
    return " ".join(words)
