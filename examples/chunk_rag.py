"""ragtrail over a plain chunk-id RAG (no subforest): paragraphs of Markdown files are the nodes.

Run: uv run python examples/chunk_rag.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from ragtrail import GenericResolver, SQLiteStore, TrajectoryStore, turn
from ragtrail.normalize import normalize, stopwords_for
from ragtrail.resolver import text_hash

CORPUS = Path(__file__).parent / "corpus"
STOPWORDS = stopwords_for(["en"])


@dataclass
class Chunk:
    label: str
    text: str


def load_chunks(root: Path = CORPUS) -> dict[str, Chunk]:
    """Split every Markdown file into paragraph chunks with ids c1, c2, … and heading breadcrumbs."""
    chunks: dict[str, Chunk] = {}
    for path in sorted(root.glob("*.md")):
        crumbs: list[str] = []
        for block in path.read_text().split("\n\n"):
            block = block.strip()
            if block.startswith("#"):
                heading, _, rest = block.partition("\n")
                level = len(heading) - len(heading.lstrip("#"))
                crumbs = [*crumbs[: level - 1], heading.lstrip("# ")]
                block = rest.strip()
            if block:
                chunks[f"c{len(chunks) + 1}"] = Chunk(" › ".join(crumbs), block)
    return chunks


def terms(text: str) -> set[str]:
    return set(normalize(text, stopwords=STOPWORDS).split())


def search(chunks: dict[str, Chunk], query: str, k: int = 3) -> list[str]:
    q = terms(query)
    scored = sorted(
        ((len(q & terms(c.label + " " + c.text)), cid) for cid, c in chunks.items()), reverse=True
    )
    return [cid for score, cid in scored[:k] if score > 0]


@dataclass
class TurnReport:
    query: str
    mode: str
    tool_calls: int
    cited: list[str]
    rendered: str


def ask(store: TrajectoryStore, chunks: dict[str, Chunk], query: str, scope: str = "larch") -> TurnReport:
    """One scripted agent turn: use the recalled path if any, otherwise search and read."""
    resolver = GenericResolver(
        hash_fn=lambda cid: text_hash(chunks[cid].text) if cid in chunks else None,
        read_fn=lambda cid, max_tokens: chunks[cid].text,
        label_fn=lambda cid: chunks[cid].label if cid in chunks else cid,
    )
    calls = 0
    with turn(store, resolver, scope, query) as t:
        if t.recall.mode == "prefetch":
            cited = [n.node_id for n in t.recall.nodes]
        elif t.recall.mode == "hint":
            cited = [n.node_id for n in t.recall.nodes]
            for cid in cited:
                calls += 1
                t.step("read", {"id": cid}, [cid])
        else:
            calls += 1
            found = search(chunks, query)
            t.step("search", {"query": query}, found)
            for cid in found:
                calls += 1
                t.step("read", {"id": cid}, [cid])
            cited = found[:2]
        t.cite(cited)
        t.accept("verified")
    return TurnReport(query, t.recall.mode, calls, cited, t.recall.rendered)


def run(db: str = ":memory:") -> list[TurnReport]:
    chunks = load_chunks()
    with SQLiteStore(db) as store:
        reports = [
            ask(store, chunks, "How do I reset my password?"),
            ask(store, chunks, "I forgot my password, how can I reset it?"),
        ]
        email = next(cid for cid, c in chunks.items() if c.text.startswith("Password reset emails"))
        chunks[email] = Chunk(chunks[email].label, "Password reset links now expire after 2 hours.")
        reports.append(ask(store, chunks, "I forgot my password, how can I reset it?"))
    return reports


def main() -> int:
    for r in run():
        print(f"[{r.mode:8}] {r.tool_calls} tool calls · cited {', '.join(r.cited)} · {r.query}")
        if r.rendered:
            print("\n".join("    " + line for line in r.rendered.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
