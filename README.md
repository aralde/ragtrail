# ragtrail

**Reuse the retrieval paths your agent already solved.**

`ragtrail` is a trajectory cache for agentic RAG. It records the *path* an agent took to a cited answer (the searches
it ran, the nodes it opened, the ones it cited) and hands that path back when a similar question arrives, so the
agent skips the orientation phase. Paths are invalidated by content hash when the underlying nodes change.

It caches the path, never the answer.

> Status: early development. See `PLAN.md`.

## Development

```bash
uv sync
uv run ruff check . && uv run mypy src && uv run pytest
```

## License

MIT
