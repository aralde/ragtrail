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

## Evaluation (WixQA, early)

Full report: [`reports/wixqa-eval.md`](reports/wixqa-eval.md). Small Haiku pilots through `claude -p`, so treat the
numbers as directional.

| Scenario, matcher | Test questions matched | Matches pointing at a gold article | Agent pilot: warm vs cold |
|---|---|---|---|
| Repeat traffic, lexical | 25/200 | 100% | −0.7 tool calls, −23% input tokens, judge 73% → 88% (n = 30) |
| Repeat traffic, **+ embeddings** | **179/200** | **100%** | **−1.2 tool calls (−39%), −30% input tokens, judge 78% → 90%** (n = 30) |
| Disjoint questions, lexical | 11/200 | 36% | no measurable effect (n = 20) |
| Disjoint questions, + embeddings | 55/200 | 47% | no measurable effect; judge 75% → 75% (n = 20) |

- **Repeat traffic** means the same question asked again in other words: warm-up on WixQA-ExpertWritten, test on
  one Haiku paraphrase of each. **Disjoint** uses different WixQA splits for warm-up and test, which barely
  repeat each other.
- With embeddings, a paraphrased question finds its earlier path 9 times in 10. On the questions in the pilot,
  the warm agent needs about a third fewer calls, and judged accuracy does not drop (+11.7 points, 95% CI 0 to
  +23).
- On disjoint questions the cache rarely fires, and its wrong hints did not lower judged accuracy in the pilot,
  but the CI is wide (±17.5 points).
- **Limits.** Pilots are small and stratified (they over-sample cache hits), the judge is the same small model,
  and warm-up trails are oracle citations.

Reproduce (needs subforest installed alongside and the `claude` CLI):

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
