"""`NodeResolver`: how ragtrail sees the caller's index (current content hashes, labels and text)."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from typing import Protocol, runtime_checkable


def text_hash(text: str) -> str:
    """Stable content hash of a node's text (sha256 hex, first 16 chars).

    >>> text_hash("hello")
    '2cf24dba5fb0a30e'
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def estimate_tokens(text: str) -> int:
    """Rough token count, `ceil(chars / 4)`; no tokenizer dependency.

    >>> estimate_tokens("abcde")
    2
    """
    return math.ceil(len(text) / 4)


@runtime_checkable
class NodeResolver(Protocol):
    """Read-only view of the caller's index. Node ids are opaque strings (subforest, chunk or doc ids)."""

    def content_hash(self, node_id: str) -> str | None:
        """Current content hash of the node, or `None` if it no longer exists."""
        ...

    def label(self, node_id: str) -> str:
        """Human-readable breadcrumb such as `"Authentication › Tokens"`; may simply return `node_id`."""
        ...

    def read(self, node_id: str, max_tokens: int) -> str:
        """Current text of the node, ideally within `max_tokens`. Callers skip text that is still too long."""
        ...


class GenericResolver:
    """`NodeResolver` built from plain callables, for any RAG stack.

    >>> docs = {"c1": "Tokens expire after one hour."}
    >>> r = GenericResolver(
    ...     hash_fn=lambda i: text_hash(docs[i]) if i in docs else None,
    ...     read_fn=lambda i, max_tokens: docs[i],
    ...     label_fn=lambda i: "Auth › Tokens",
    ... )
    >>> r.content_hash("c1") == text_hash(docs["c1"]), r.content_hash("gone")
    (True, None)
    >>> r.label("c1")
    'Auth › Tokens'
    """

    def __init__(
        self,
        hash_fn: Callable[[str], str | None],
        read_fn: Callable[[str, int], str],
        label_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._hash_fn = hash_fn
        self._read_fn = read_fn
        self._label_fn = label_fn

    def content_hash(self, node_id: str) -> str | None:
        return self._hash_fn(node_id)

    def label(self, node_id: str) -> str:
        return node_id if self._label_fn is None else self._label_fn(node_id)

    def read(self, node_id: str, max_tokens: int) -> str:
        return self._read_fn(node_id, max_tokens)
