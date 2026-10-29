"""Store key layout shared by every backend. Every key starts with its scope."""

from __future__ import annotations

from ragtrail.models import KEY_SEPARATOR, _check_key_segment

TRAJECTORY_PREFIX = "t"
BAND_PREFIX = "b"


def trajectory_key(scope: str, trajectory_id: str) -> str:
    """Key of a trajectory item.

    >>> trajectory_key("acme", "abc")
    't#acme#abc'
    """
    _check_key_segment(scope, "scope")
    _check_key_segment(trajectory_id, "trajectory_id")
    return KEY_SEPARATOR.join((TRAJECTORY_PREFIX, scope, trajectory_id))


def band_key(scope: str, band_idx: int, band_hash: str) -> str:
    """Key of an LSH band bucket.

    >>> band_key("acme", 3, "9f2c")
    'b#acme#3#9f2c'
    """
    _check_key_segment(scope, "scope")
    _check_key_segment(band_hash, "band_hash")
    if band_idx < 0:
        raise ValueError(f"band_idx must be >= 0: {band_idx}")
    return KEY_SEPARATOR.join((BAND_PREFIX, scope, str(band_idx), band_hash))


def band_key_in_scope(key: str, scope: str) -> bool:
    """True if `key` is a well-formed band key belonging to `scope`.

    >>> band_key_in_scope("b#acme#3#9f2c", "acme")
    True
    >>> band_key_in_scope("b#acme-eu#3#9f2c", "acme")
    False
    """
    parts = key.split(KEY_SEPARATOR)
    return (
        len(parts) == 4
        and parts[0] == BAND_PREFIX
        and parts[1] == scope
        and parts[2].isdigit()
        and bool(parts[3])
    )
