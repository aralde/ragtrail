"""ragtrail with subforest: node ids are subforest short ids (`n3`), labels are its breadcrumbs.

Needs subforest installed next to ragtrail, e.g.:
    uv run --with-editable ../subforest python examples/subforest_rag.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from subforest import TreeStore
from subforest.build import build_corpus
from subforest.retrievers import FTS5Retriever
from subforest.tools import Toolkit

from ragtrail import SQLiteStore, TrajectoryStore, turn
from ragtrail.subforest import SubforestResolver

CORPUS = Path(__file__).parent / "corpus"


@dataclass
class TurnReport:
    query: str
    mode: str
    tool_calls: int
    cited: list[str]
    rendered: str


def build_tree(root: Path = CORPUS) -> TreeStore:
    tree = TreeStore()
    build_corpus(root, corpus_id="larch").write(tree)
    return tree


def ask(store: TrajectoryStore, tree: TreeStore, query: str, scope: str = "larch") -> TurnReport:
    """One scripted agent turn: use the recalled path if any, otherwise search and read the hits."""
    tools = Toolkit(tree, FTS5Retriever(tree))
    calls = 0
    with turn(store, SubforestResolver(tree), scope, query) as t:
        if t.recall.mode != "miss":
            cited = [n.node_id for n in t.recall.nodes]
            if t.recall.mode == "hint":
                for node_id in cited:
                    calls += 1
                    t.step("read", {"node_id": node_id}, [node_id])
        else:
            calls += 1
            result = tools.call("search", query=query)
            hit_nodes = list(dict.fromkeys(h["node"] for h in result.data["hits"]))
            t.step("search", {"query": query}, result.data.get("nodes", []))
            for node_id in hit_nodes[:3]:
                calls += 1
                tools.call("read", node_id=node_id)
                t.step("read", {"node_id": node_id}, [node_id])
            cited = hit_nodes[:2]
        t.cite(cited)
        t.accept("verified")
    return TurnReport(query, t.recall.mode, calls, cited, t.recall.rendered)


def run(db: str = ":memory:") -> list[TurnReport]:
    tree = build_tree()
    with SQLiteStore(db) as store:
        reports = [
            ask(store, tree, "How do I refresh an expired access token?"),
            ask(store, tree, "how can I refresh my access token when it expires"),
        ]
        cited = reports[0].cited[-1]
        node = tree.get_node(int(cited[1:]))
        doc = next(a for a in reversed(tree.ancestors(node.id)) if a.kind == "doc")
        text = tree.doc_text(doc.id) or ""
        assert node.span is not None
        start, end = node.span
        edited = text[:start] + text[start:end].replace("60 minutes", "15 minutes").replace(
            "30 days", "7 days"
        )
        tree.connection.execute(
            "UPDATE doc_texts SET text = ? WHERE node_id = ?", (edited + text[end:], doc.id)
        )
        reports.append(ask(store, tree, "how can I refresh my access token when it expires"))
    return reports


def main() -> int:
    for r in run():
        print(f"[{r.mode:8}] {r.tool_calls} tool calls · cited {', '.join(r.cited)} · {r.query}")
        if r.rendered:
            print("\n".join("    " + line for line in r.rendered.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
