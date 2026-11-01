# ragtrail

**Reuse the retrieval paths your agent already solved.**

`ragtrail` is a trajectory cache for agentic RAG. It records the *path* an agent took to a cited answer (the searches
it ran, the nodes it opened, the ones it cited) and hands that path back when a similar question arrives, so the
agent skips the orientation phase. Paths are invalidated by content hash when the underlying nodes change.

It caches the path, never the answer.

> Status: early development. See `PLAN.md`.

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
uv sync
uv run ruff check . && uv run mypy src && uv run pytest
```

## License

MIT
