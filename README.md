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

## Development

```bash
uv sync
uv run ruff check . && uv run mypy src && uv run pytest
```

## License

MIT
