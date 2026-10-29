from dataclasses import dataclass, field
from pathlib import Path

import pytest

from ragtrail.resolver import NodeResolver, text_hash
from ragtrail.subforest import SubforestNode, SubforestResolver

DOC = "# Auth\n\nIntro.\n\n## Tokens\n\nThey expire.\n\n## Refresh\n\nPOST /oauth/token.\n"


@dataclass(frozen=True)
class FakeNode:
    id: int
    kind: str
    title: str
    span: tuple[int, int] | None
    parent: int | None = None


@dataclass
class FakeTree:
    nodes: dict[int, FakeNode] = field(default_factory=dict)
    texts: dict[int, str] = field(default_factory=dict)

    def get_node(self, node_id: int) -> SubforestNode:
        try:
            return self.nodes[node_id]
        except KeyError:
            raise KeyError(f"unknown node {node_id}") from None

    def ancestors(self, node_id: int) -> list[SubforestNode]:
        out: list[SubforestNode] = []
        parent = self.nodes[node_id].parent
        while parent is not None:
            out.insert(0, self.nodes[parent])
            parent = self.nodes[parent].parent
        return out

    def doc_text(self, node_id: int) -> str | None:
        return self.texts.get(node_id)


def span(text: str, start_marker: str, end_marker: str | None = None) -> tuple[int, int]:
    start = DOC.index(start_marker)
    return start, DOC.index(end_marker) if end_marker else len(DOC)


@pytest.fixture
def tree() -> FakeTree:
    return FakeTree(
        nodes={
            1: FakeNode(1, "site", "docs/", None),
            2: FakeNode(2, "dir", "guides", None, parent=1),
            3: FakeNode(3, "doc", "Auth", (0, len(DOC)), parent=2),
            4: FakeNode(4, "section", "Tokens", span(DOC, "## Tokens", "## Refresh"), parent=3),
            5: FakeNode(5, "section", "Refresh", span(DOC, "## Refresh"), parent=3),
        },
        texts={3: DOC},
    )


def test_is_a_node_resolver(tree: FakeTree) -> None:
    assert isinstance(SubforestResolver(tree), NodeResolver)


def test_labels_skip_site(tree: FakeTree) -> None:
    r = SubforestResolver(tree)
    assert r.label("n4") == "guides › Auth › Tokens"
    assert r.label("3") == "guides › Auth"
    assert r.label("n99") == "n99"
    assert r.label("chunk-7") == "chunk-7"


def test_read_and_hash_use_the_node_span(tree: FakeTree) -> None:
    r = SubforestResolver(tree)
    assert r.read("n4", 100) == "## Tokens\n\nThey expire."
    assert r.content_hash("n4") == text_hash("## Tokens\n\nThey expire.")
    assert r.content_hash("n3") == text_hash(DOC.strip())


def test_unreadable_or_missing_nodes(tree: FakeTree) -> None:
    r = SubforestResolver(tree)
    for node_id in ("n1", "n2", "n99", "x"):
        assert r.content_hash(node_id) is None
        assert r.read(node_id, 100) == ""
    tree.texts.clear()
    assert r.content_hash("n4") is None


def test_editing_a_subsection_changes_the_parent_hash(tree: FakeTree) -> None:
    r = SubforestResolver(tree)
    before = {n: r.content_hash(n) for n in ("n3", "n4", "n5")}
    tree.texts[3] = DOC.replace("They expire.", "They expire!")
    after = {n: r.content_hash(n) for n in ("n3", "n4", "n5")}
    assert after["n3"] != before["n3"]
    assert after["n4"] != before["n4"]
    assert after["n5"] == before["n5"]


def test_against_real_subforest(tmp_path: Path) -> None:
    pytest.importorskip("subforest")
    from subforest import TreeStore
    from subforest.build import build_corpus

    (tmp_path / "auth.md").write_text(DOC)
    store = TreeStore()
    build_corpus(tmp_path, corpus_id="docs").write(store)
    r = SubforestResolver(store)
    tokens = next(n for n in (store.get_node(i) for i in range(1, 6)) if n.title == "Tokens")
    assert r.label(tokens.short_id) == "Auth › Tokens"
    assert r.read(tokens.short_id, 100) == "## Tokens\n\nThey expire."
