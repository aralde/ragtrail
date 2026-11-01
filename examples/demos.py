"""Six small, deterministic demos of the behaviours the evaluation measures. No API, no network, no subforest.

Run all:  uv run python examples/demos.py
Run one:  uv run python examples/demos.py freshness
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from ragtrail import GenericResolver, SQLiteStore, TrajectoryStore, recall, turn
from ragtrail.match import normalize_query, signature, similarity
from ragtrail.models import Outcome
from ragtrail.resolver import text_hash

CORPUS = {
    "c1": "Access tokens expire after 60 minutes. An expired token returns HTTP 401 token_expired.",
    "c2": "To refresh an access token, POST the refresh token to /oauth/token with grant_type=refresh_token.",
    "c3": "Refresh tokens are valid for 30 days and are rotated on every use.",
    "c4": "Invoices are issued on the first day of each month and can be downloaded as PDF.",
    "c5": "To delete an account, an admin opens Settings and chooses Delete workspace.",
    "p1": "We fine-tune on GLUE, SQuAD v1.1, SQuAD v2.0 and SWAG.",
    "p2": "We compare against OpenAI GPT and ELMo-based systems.",
}


@dataclass
class Demo:
    name: str
    claim: str
    lines: list[str] = field(default_factory=list)
    facts: dict[str, object] = field(default_factory=dict)

    def say(self, line: str) -> None:
        self.lines.append(line)


def resolver(docs: dict[str, str]) -> GenericResolver:
    return GenericResolver(
        hash_fn=lambda i: text_hash(docs[i]) if i in docs else None,
        read_fn=lambda i, max_tokens: docs[i],
    )


def search(docs: dict[str, str], query: str, k: int = 3) -> list[str]:
    q = set(normalize_query(query).split())
    scored = sorted(((len(q & set(normalize_query(t).split())), i) for i, t in docs.items()), reverse=True)
    return [i for score, i in scored[:k] if score > 0]


def agent(
    store: TrajectoryStore,
    docs: dict[str, str],
    query: str,
    scope: str = "acme",
    cite: list[str] | None = None,
    outcome: Outcome | None = "verified",
) -> tuple[str, int, list[str]]:
    """Scripted agent turn: (recall mode, tool calls, cited ids). `outcome=None`: answer rejected."""
    calls = 0
    with turn(store, resolver(docs), scope, query) as t:
        if t.recall.mode == "prefetch":
            cited = [n.node_id for n in t.recall.nodes]
        elif t.recall.mode == "hint":
            cited = [n.node_id for n in t.recall.nodes]
            for i in cited:
                calls += 1
                t.step("read", {"id": i}, [i])
        else:
            found = search(docs, query)
            calls += 1 + len(found)
            t.step("search", {"q": query}, found)
            for i in found:
                t.step("read", {"id": i}, [i])
            cited = cite if cite is not None else found[:2]
        t.cite(cited)
        if outcome is not None:
            t.accept(outcome)
    return t.recall.mode, calls, cited


def demo_reuse() -> Demo:
    d = Demo("reuse", "A paraphrased repeat reuses the recorded path instead of searching again.")
    with SQLiteStore(":memory:") as store:
        cold = agent(store, CORPUS, "How do I refresh an expired access token?", cite=["c2", "c1"])
        warm = agent(store, CORPUS, "how can I refresh an access token that expired")
    d.say(f"cold: {cold[0]:8} {cold[1]} tool calls, cited {cold[2]}")
    d.say(f"warm: {warm[0]:8} {warm[1]} tool calls, cited {warm[2]}")
    d.facts = {
        "cold_calls": cold[1],
        "warm_calls": warm[1],
        "warm_mode": warm[0],
        "same_cites": cold[2] == warm[2],
    }
    return d


def demo_freshness() -> Demo:
    d = Demo("freshness", "An edited source is never served from cache; a copy cache serves the old text.")
    docs = dict(CORPUS)
    query = "How long are refresh tokens valid and how do I use one?"
    with SQLiteStore(":memory:") as store:
        agent(store, docs, query, cite=["c3", "c2"])
        copy_cache = {normalize_query(query): {i: docs[i] for i in ("c3", "c2")}}
        docs["c3"] = "Refresh tokens are valid for 14 days and are rotated on every use."
        result = recall(store, resolver(docs), query, "acme")
    copied = copy_cache[normalize_query(query)]["c3"]
    served = " ".join(docs[n.node_id] for n in result.nodes) if result.mode == "prefetch" else ""
    d.say(f"copy cache serves:  {copied!r}")
    d.say(f"ragtrail mode:      {result.mode}, still-valid nodes {[n.node_id for n in result.nodes]}")
    d.say("ragtrail drops the edited node, so the agent re-reads it and sees '14 days'")
    d.facts = {
        "copy_is_stale": "30 days" in copied,
        "mode": result.mode,
        "kept": [n.node_id for n in result.nodes],
        "served_stale": "30 days" in served,
    }
    return d


def demo_deleted() -> Demo:
    d = Demo("deleted", "If every cited node changed or vanished, recall misses and marks the trail stale.")
    docs = dict(CORPUS)
    query = "When are invoices issued?"
    with SQLiteStore(":memory:") as store:
        agent(store, docs, query, cite=["c4"])
        trail_id = recall(store, resolver(docs), query, "acme").trajectory_id
        del docs["c4"]
        result = recall(store, resolver(docs), query, "acme")
        trail = store.get("acme", trail_id) if trail_id else None
    stale = trail is not None and trail.stale
    d.say(f"after deleting c4: mode {result.mode}, trail marked stale: {stale}")
    d.facts = {"mode": result.mode, "stale": stale}
    return d


def demo_fixed_context() -> Demo:
    d = Demo("fixed-context", "A fixed prefix (paper title) makes different questions match; scope fixes it.")
    title = "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"
    q1, q2 = "Which datasets do they use?", "Which baselines do they compare to?"
    a, b = f'About "{title}": {q1}', f'About "{title}": {q2}'
    titled = similarity(signature(normalize_query(a)), signature(normalize_query(b)))
    bare = similarity(signature(normalize_query(q1)), signature(normalize_query(q2)))
    with SQLiteStore(":memory:") as store:
        agent(store, CORPUS, a, scope="acme", cite=["p1"])
        in_query = recall(store, resolver(CORPUS), b, "acme")
        agent(store, CORPUS, q1, scope="acme-bert", cite=["p1"])
        in_scope = recall(store, resolver(CORPUS), q2, "acme-bert")
    handed = [n.node_id for n in in_query.nodes]
    d.say(f"title in query: similarity {titled:.2f} -> {in_query.mode}, hands back {handed}")
    d.say(f"title in scope: similarity {bare:.2f} -> {in_scope.mode}")
    d.facts = {"in_query": in_query.mode, "in_scope": in_scope.mode, "titled": titled, "bare": bare}
    return d


def demo_scope() -> Demo:
    d = Demo("scope", "A trail recorded for one tenant or permission group is invisible to another.")
    query = "How do I delete my account?"
    with SQLiteStore(":memory:") as store:
        agent(store, CORPUS, query, scope="acme", cite=["c5"])
        own = recall(store, resolver(CORPUS), query, "acme")
        other = recall(store, resolver(CORPUS), query, "globex")
    d.say(f"same tenant: {own.mode}; other tenant: {other.mode}")
    d.facts = {"own": own.mode, "other": other.mode}
    return d


def demo_admission() -> Demo:
    d = Demo("admission", "Only accepted answers are recorded; an accepted wrong path is replayed as-is.")
    query = "How long do access tokens last?"
    with SQLiteStore(":memory:") as store:
        agent(store, CORPUS, query, cite=["c4"], outcome=None)
        rejected = recall(store, resolver(CORPUS), query, "acme")
    with SQLiteStore(":memory:") as store:
        agent(store, CORPUS, query, cite=["c4"], outcome="accepted")
        accepted = recall(store, resolver(CORPUS), query, "acme")
    wrong = [n.node_id for n in accepted.nodes]
    d.say(f"wrong answer rejected: next turn {rejected.mode}")
    d.say(
        f"wrong answer accepted: next turn {accepted.mode} with {wrong} (an invoice chunk, not token expiry)"
    )
    d.facts = {"rejected": rejected.mode, "accepted": accepted.mode, "wrong": wrong}
    return d


DEMOS: dict[str, Callable[[], Demo]] = {
    "reuse": demo_reuse,
    "freshness": demo_freshness,
    "deleted": demo_deleted,
    "fixed-context": demo_fixed_context,
    "scope": demo_scope,
    "admission": demo_admission,
}


def main(argv: list[str] | None = None) -> int:
    names = (argv if argv is not None else sys.argv[1:]) or list(DEMOS)
    unknown = [n for n in names if n not in DEMOS]
    if unknown:
        print(f"unknown demo(s): {', '.join(unknown)}; choose from {', '.join(DEMOS)}", file=sys.stderr)
        return 2
    for name in names:
        d = DEMOS[name]()
        print(f"== {d.name}: {d.claim}")
        for line in d.lines:
            print("   " + line)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
