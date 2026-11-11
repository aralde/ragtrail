# ragtrail

**Reuse the retrieval paths your agent already solved.**

`ragtrail` is a trajectory cache for agentic RAG. It records the *path* an agent took to a cited answer (the searches
it ran, the nodes it opened, the ones it cited) and hands that path back when a similar question arrives, so the
agent skips the orientation phase. Paths are invalidated by content hash when the underlying nodes change.

It caches the path, never the answer.

[![CI](https://github.com/aralde/ragtrail/actions/workflows/ci.yml/badge.svg)](https://github.com/aralde/ragtrail/actions/workflows/ci.yml)

> Status: alpha (0.1.0, not on PyPI yet). The core, the MCP server and the evaluation harness work and are tested;
> the cloud stores in [`PLAN.md`](PLAN.md) (M6–M8) are not built. Write-up:
> [Building ragtrail](https://aralde.dev/blog/building-ragtrail).

## Install

```bash
pip install 'git+https://github.com/aralde/ragtrail.git'            # core: stdlib + sqlite3 + pydantic
pip install 'ragtrail[mcp,embed] @ git+https://github.com/aralde/ragtrail.git'   # MCP server, embedding matcher
```

Python 3.11 or newer.

## Use it from Python

Wrap one agent turn. On entry you get the recalled path (if any); on exit an accepted turn is stored.

```python
from ragtrail import GenericResolver, SQLiteStore, turn
from ragtrail.resolver import text_hash

resolver = GenericResolver(
    hash_fn=lambda node_id: text_hash(docs[node_id]) if node_id in docs else None,  # None = deleted
    read_fn=lambda node_id, max_tokens: docs[node_id],
)

with SQLiteStore("trails.db") as store:
    with turn(store, resolver, scope="my-team", query=question) as t:
        if t.recall.mode != "miss":
            print(t.recall.rendered)  # nodes to start from, or their current text
        # ... run your agent, record what it did and what it cited ...
        t.step("search", {"query": question}, found_ids)
        t.cite(cited_ids)
        t.accept("verified")  # no accept, no trail
```

A runnable version over plain chunk ids is in [`examples/chunk_rag.py`](examples/chunk_rag.py); the subforest one is
[`examples/subforest_rag.py`](examples/subforest_rag.py).

## How it works

1. **Match.** The question is normalized and matched against stored questions with MinHash/LSH (stdlib only), or by
   embeddings if you enable them. Lookup is a handful of key reads, so any key-value store can back it.
2. **Validate.** Every cited node is re-hashed against the live index. All unchanged: `prefetch` (current node text,
   within a token budget). Some changed: `hint` with only the still-valid nodes. All changed: `miss`, and the trail
   is marked stale.
3. **Admit.** A trail is written only with a positive signal (verified citations, user feedback, or an explicit
   accept). Scopes (tenant, document, permission group) never mix.

Design decisions, with the numbers that drove them, are in [`docs/decisions.md`](docs/decisions.md).

## Limitations

- Savings come only from repeated or reworded questions; the evaluation uses model-written repeats, so real traffic
  will save less.
- Hash validation catches *changed* nodes, not *new* documents that would now be better evidence; only the TTL
  covers that.
- Admission quality decides safety. A path from a wrong answer sends the agent back to the same mistake.
- Evaluated with one agent model (Haiku) and one judge (Sonnet, checked on 40 labels, not human-labelled).
- The evaluation harness needs [subforest](https://github.com/aralde/subforest) and the `claude` CLI; the library
  itself does not depend on either.

## MCP server

```bash
pip install 'ragtrail[mcp]'
ragtrail serve --db trails.db --scope my-team --subforest corpus.db
```

The server exposes two tools: `recall(query, budget_tokens?)` at the start of a question and
`record(query, cited, outcome?, steps?)` after a grounded answer. Each server is bound to one `--scope`.

Add `--embed` (needs `pip install 'ragtrail[embed]'`) to also match paraphrases by embeddings. It uses a local
CPU model, `BAAI/bge-small-en-v1.5` by default, so there is no API cost.

How it checks nodes:

- `--subforest corpus.db`: a subforest index. Node hashes are checked on every recall and texts are prefetched.
- `--resolver mypkg.index:make_resolver`: any `NodeResolver` for your own index.
- Neither: unverified mode. Recall only hints node ids and never prefetches.

Claude Code:

```bash
claude mcp add ragtrail -- ragtrail serve --db ~/.ragtrail/trails.db --scope my-team --subforest corpus.db
```

Other MCP clients (Claude Desktop, Cursor, …) use the same command in their JSON config:

```json
{
  "mcpServers": {
    "ragtrail": {
      "command": "ragtrail",
      "args": ["serve", "--db", "/path/to/trails.db", "--scope", "my-team", "--subforest", "/path/to/corpus.db"]
    }
  }
}
```

Run it next to your retrieval tools (for example subforest's own MCP server). `ragtrail purge --db trails.db`
deletes expired trails.

## Evaluation

Summary and details: [`reports/README.md`](reports/README.md). Haiku agent and Sonnet judge through `claude -p`.

**Repeat traffic** (the same question asked again in other words), all questions, cache off vs on.

The realistic run uses trails the agent recorded itself on WixQA (n = 200):

- Tool calls: 3.4 → 2.1.
- Input tokens: −33%.
- Judged correct: 69.8% → 74.2% (+4.5, 95% CI −0.8 to +9.8): no accuracy loss.

With oracle trails, which cite the gold evidence, the per-hit gains are larger. Treat them as an upper bound:

| Dataset | n | Tool calls | Input tokens | Judged correct |
|---|---|---|---|---|
| WixQA help center | 200 | 3.4 → 2.2 | −28% | 69.8% → 86.2% |
| QASPER papers | 400 | 4.1 → 1.5 | −57% | 60.8% → 71.6% |

- **Only record trails from answers you trust.** When the recorded answer was wrong, warm accuracy fell from 50% to
  21% on those questions; when it was right, it rose from 79% to 87%.
- **Put fixed context (document, product, customer) in `scope`.** If a paper's title is part of the matched text, any
  question about that paper looks similar and gets the wrong sections.
- **Savings come only from repeated questions.** Every test question here is a model-written repeat, so the cache
  saves less on real traffic, where fewer questions repeat. Related work:
  [`docs/related-work`](docs/related-work/README.md).

Reproduce (needs subforest installed alongside and the `claude` CLI; add `--dataset qasper` for QASPER):

```bash
ragtrail eval fetch
ragtrail eval paraphrase
for s in disjoint repeat; do
  ragtrail eval offline --scenario $s && ragtrail eval offline --scenario $s --embed
done
ragtrail eval agent --scenario repeat --n 30 [--embed]    # likewise disjoint with --n 20
ragtrail eval judge --scenario repeat [--embed]
ragtrail eval report
```

## Demos

`uv run python examples/demos.py` runs six small offline cases, no API needed: paraphrase reuse, an edited source
(ragtrail drops it; a copy cache serves the old text), a deleted source, the fixed-context false match and its scope
fix, tenant isolation, and admission gating. Pass a name (`freshness`, `fixed-context`, ...) to run one.

## Development

```bash
uv sync --all-extras
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT
