"""Fixture corpus with mutable node texts and a scripted agent that walks it like an agentic RAG loop."""

import json
from pathlib import Path

from ragtrail.models import Outcome
from ragtrail.recall import recall
from ragtrail.recorder import Recorder
from ragtrail.resolver import GenericResolver, text_hash
from ragtrail.store import TrajectoryStore

FIXTURE = Path(__file__).parent / "fixtures" / "corpus.json"


class Corpus:
    def __init__(self) -> None:
        nodes = json.loads(FIXTURE.read_text())["nodes"]
        self.labels: dict[str, str] = {k: v["label"] for k, v in nodes.items()}
        self.texts: dict[str, str] = {k: v["text"] for k, v in nodes.items()}
        self.reads = 0

    def edit(self, node_id: str, text: str) -> None:
        self.texts[node_id] = text

    def resolver(self) -> GenericResolver:
        def read(node_id: str, max_tokens: int) -> str:
            self.reads += 1
            return self.texts[node_id]

        return GenericResolver(
            hash_fn=lambda i: text_hash(self.texts[i]) if i in self.texts else None,
            read_fn=read,
            label_fn=lambda i: self.labels.get(i, i),
        )

    def search(self, query: str) -> list[str]:
        words = set(query.lower().split())
        scored = [(sum(w in t.lower() for w in words), k) for k, t in self.texts.items()]
        return [k for s, k in sorted(scored, reverse=True) if s > 0][:3]


class ScriptedAgent:
    """Searches, opens the results, and cites `answer_nodes`. Uses a recall hit to skip orientation."""

    def __init__(self, corpus: Corpus, store: TrajectoryStore, scope: str = "acme") -> None:
        self.corpus = corpus
        self.store = store
        self.scope = scope
        self.tool_calls = 0

    def ask(self, query: str, answer_nodes: list[str], outcome: Outcome | None = "verified") -> str:
        resolver = self.corpus.resolver()
        hit = recall(self.store, resolver, query, self.scope)
        rec = Recorder(self.store, resolver, self.scope, query)
        if hit.mode == "prefetch":
            rec.cite(n.node_id for n in hit.nodes)
        elif hit.mode == "hint":
            for ref in hit.nodes:
                self.tool_calls += 1
                rec.step("read", {"node": ref.node_id}, [ref.node_id])
            rec.cite(n.node_id for n in hit.nodes)
        else:
            for q in (query, " ".join(query.split()[:2])):
                self.tool_calls += 1
                rec.step("search", {"q": q}, self.corpus.search(q))
            for node_id in answer_nodes:
                self.tool_calls += 1
                rec.step("read", {"node": node_id}, [node_id])
            rec.cite(answer_nodes)
        rec.commit(outcome)
        return hit.mode
