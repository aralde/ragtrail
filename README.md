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

## Evaluation (WixQA, early)

Full report: [`reports/wixqa-eval.md`](reports/wixqa-eval.md). Small Haiku pilots through `claude -p`, so treat the
numbers as directional.

- **Repeat traffic** (the same question asked again in other words). On questions the cache recognizes, the warm
  agent makes 0.7 fewer tool calls (95% CI 0.17 to 1.27), uses 23% fewer input tokens, and its judged accuracy
  does not drop (73% → 88%, CI +2 to +28 points; n = 30). Lexical matching recognizes only 25 of 200 paraphrases,
  but every match points at the right article.
- **Disjoint questions** (warm-up and test sets from different WixQA splits). Only 11 of 200 test questions match
  anything, and the agent pilot shows no measurable effect either way (accuracy −2.5 points, CI −12.5 to +7.5;
  n = 20).
- **Limits.** The matcher is lexical (MinHash), so paraphrases far from the original miss; an embedding matcher is
  the planned next step. The judge is the same small model, warm-up trails are oracle citations, and the pilots
  over-sample cache hits.

Reproduce (needs subforest installed alongside and the `claude` CLI):

```bash
ragtrail eval fetch
ragtrail eval paraphrase
ragtrail eval offline --scenario disjoint && ragtrail eval offline --scenario repeat
ragtrail eval agent --scenario repeat --n 30 && ragtrail eval agent --scenario disjoint --n 20
ragtrail eval judge --scenario repeat && ragtrail eval judge --scenario disjoint
ragtrail eval report
```

## Development

```bash
uv sync
uv run ruff check . && uv run mypy src && uv run pytest
```

## License

MIT
