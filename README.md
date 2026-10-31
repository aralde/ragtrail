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

**Repeat traffic** (the same question asked again in other words), all questions, cache off vs on:

| Dataset | n | Tool calls | Input tokens | Judged correct |
|---|---|---|---|---|
| WixQA help center | 200 | 3.4 → 2.2 | −28% | 69.8% → 86.2% (+16.5, 95% CI +11.5 to +21.2) |
| QASPER papers | 400 | 4.1 → 1.5 | −57% | 60.8% → 71.6% (+10.9, 95% CI +7.2 to +14.4) |

- With embeddings, 9 in 10 paraphrased help-center questions find their earlier path, and every match points at the
  right article.
- Put fixed context (document, product, customer) in `scope`. If a paper's title is part of the matched text, any
  question about that paper looks similar and gets the wrong sections.
- Questions that do not repeat get little from the cache. Paraphrases are model-written and warm-up trails are
  oracle citations, so real traffic will repeat less cleanly.

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

## Development

```bash
uv sync
uv run ruff check . && uv run mypy src && uv run pytest
```

## License

MIT
