"""`SubforestResolver`: node ids, breadcrumbs and section hashes from a subforest `TreeStore`.

Typed against the few `TreeStore` methods it uses, so this module does not import subforest.
"""

from __future__ import annotations

import re
from typing import Protocol

from ragtrail.resolver import text_hash

_NODE_ID = re.compile(r"^n?(\d+)$")


class SubforestNode(Protocol):
    @property
    def id(self) -> int: ...
    @property
    def kind(self) -> str: ...
    @property
    def title(self) -> str: ...
    @property
    def span(self) -> tuple[int, int] | None: ...


class SubforestTree(Protocol):
    """The part of `subforest.TreeStore` this resolver needs."""

    def get_node(self, node_id: int) -> SubforestNode: ...
    def ancestors(self, node_id: int) -> list[SubforestNode]: ...
    def doc_text(self, node_id: int) -> str | None: ...


def parse_node_id(node_id: str) -> int | None:
    """Accept subforest's `n31` or `31`; `None` for anything else.

    >>> parse_node_id("n31"), parse_node_id("31"), parse_node_id("c31")
    (31, 31, None)
    """
    m = _NODE_ID.match(node_id.strip())
    return int(m.group(1)) if m else None


class SubforestResolver:
    """`NodeResolver` over a subforest tree. Node ids are subforest short ids (`n31`).

    A node's hash covers its whole span, subsections included: editing a subsection invalidates
    trajectories that used the parent section, because the agent read that text too.

    >>> from types import SimpleNamespace as N
    >>> doc = N(id=2, kind="doc", title="Auth", span=(0, 30))
    >>> sec = N(id=3, kind="section", title="Tokens", span=(7, 30))
    >>> site = N(id=1, kind="site", title="docs/", span=None)
    >>> tree = N(
    ...     get_node={1: site, 2: doc, 3: sec}.__getitem__,
    ...     ancestors={3: [site, doc], 2: [site], 1: []}.__getitem__,
    ...     doc_text={2: "# Auth\\n## Tokens\\nThey expire."}.get,
    ... )
    >>> r = SubforestResolver(tree)
    >>> r.label("n3"), r.read("n3", 100)
    ('Auth › Tokens', '## Tokens\\nThey expire.')
    >>> r.content_hash("n1") is None, r.content_hash("n99") is None
    (True, True)
    """

    def __init__(self, tree: SubforestTree) -> None:
        self.tree = tree

    def _node(self, node_id: str) -> SubforestNode | None:
        nid = parse_node_id(node_id)
        if nid is None:
            return None
        try:
            return self.tree.get_node(nid)
        except KeyError:
            return None

    def _text(self, node: SubforestNode) -> str | None:
        if node.span is None:
            return None
        if node.kind == "doc":
            doc_id: int | None = node.id
        else:
            doc_id = next((a.id for a in reversed(self.tree.ancestors(node.id)) if a.kind == "doc"), None)
        source = None if doc_id is None else self.tree.doc_text(doc_id)
        if source is None:
            return None
        start, end = node.span
        return source[start:end].strip()

    def content_hash(self, node_id: str) -> str | None:
        node = self._node(node_id)
        text = None if node is None else self._text(node)
        return None if text is None else text_hash(text)

    def label(self, node_id: str) -> str:
        node = self._node(node_id)
        if node is None:
            return node_id
        titles = [a.title for a in self.tree.ancestors(node.id) if a.kind != "site"]
        return " › ".join([*titles, node.title])

    def read(self, node_id: str, max_tokens: int) -> str:
        node = self._node(node_id)
        text = None if node is None else self._text(node)
        return text or ""
