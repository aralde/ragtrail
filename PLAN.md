# ragtrail — plan

Each milestone ends green: `uv run ruff check . && uv run mypy src && uv run pytest`, checkboxes ticked, commit.

## M0 — Scaffold + models + SQLite store
- [x] `uv init --lib`, `src/ragtrail/`, MIT `LICENSE`, `README.md` stub, `docs/decisions.md`
- [x] Pydantic models from `CLAUDE.md` (`NodeRef`, `Step`, `Trajectory`, `RecallResult`)
- [x] `TrajectoryStore` protocol: `put`, `get`, `candidates(scope, band_keys)`, `mark_stale`, `incr_hits`, `purge_expired`
- [x] `SQLiteStore` implementing it, with the key layout from `CLAUDE.md`, TTL honored on read and via `purge_expired`
- [x] CI (GitHub Actions): ruff, mypy, pytest on 3.11 and 3.12

**Accept:** round-trip put/get/candidates tests; expired items never returned; scopes never mix.

## M1 — Normalization + MinHash/LSH matcher
- [x] `normalize(query)`: lowercase, Unicode NFKC, strip punctuation, collapse whitespace, optional stopword list (en/es)
- [x] Shingles (word 2-grams + char 4-grams), MinHash with fixed seeds (default 126 perms), LSH bands (default 42×3, see decisions)
- [x] `similarity(sig_a, sig_b)` = estimated Jaccard; `band_keys(scope, sig)`
- [x] Tunables in one `MatchConfig`; document the precision/recall trade-off in `docs/decisions.md`

**Accept:** deterministic signatures across runs; paraphrase pairs in fixtures score above unrelated pairs; property
test that identical queries always collide in every band.

## M2 — Recorder, admission policy, recall
- [x] `NodeResolver` protocol + `GenericResolver(hash_fn, read_fn)`
- [x] `Recorder`: `step(tool, args, returned)`, `cite(node_ids)`, `commit(outcome)`; drops the turn if no positive outcome
- [x] `recall(query, scope, budget_tokens)`: candidates → rank → hash validation → `prefetch | hint | miss`
- [x] Renderer for both modes following the recall contract; budgeted
- [x] Stale handling: partial → hint; total → miss + `mark_stale`

**Accept:** scripted fake agent: turn 1 records, turn 2 with a paraphrase gets `prefetch`; after changing one node's
hash it gets `hint` without that node; after changing all, `miss`.

## M3 — Integrations
- [x] Python middleware: `with ragtrail.turn(store, resolver, scope, query) as t:` exposes `t.recall`, `t.step`, `t.cite`,
      auto-commit on exit with outcome
- [x] `ragtrail[subforest]`: `SubforestResolver` using subforest node ids and section text hashes
      (as `ragtrail.subforest`, no extra until subforest is on PyPI; see decisions)
- [x] Example: plain chunk-id RAG (no subforest) in `examples/`

**Accept:** both examples run against the fixture corpus offline.

## M4 — MCP server
- [x] `ragtrail[mcp]`: stdio server with tools `recall(query, budget_tokens?)` (scope bound per server, see decisions) and
      `record(query, steps, cited, outcome)`; `ragtrail serve --db trails.db`
- [x] README snippet for `claude mcp add …` and other MCP clients
- [x] Manual smoke test from a real MCP client; note result in `docs/decisions.md`

**Accept:** tools listed and callable; a recorded trail is recalled in the next turn.

## M5 — Eval: cold vs warm (the headline)
- [ ] `docs/datasets.md` with licenses; download script, no data committed. Start with WixQA (MIT, KB snapshot included)
- [ ] Split so warm-up and test questions are **disjoint** (e.g. warm with WixQA-Simulated + Synthetic, test on
      ExpertWritten); report leakage checks
- [ ] Agent loop with pluggable LLM (Anthropic default) and a retriever (subforest if installed, else SQLite FTS5)
- [ ] Arms: `cold` (empty trail store) vs `warm` (after warm-up); same model, same retriever
- [ ] Metrics: hit rate by mode, tool calls, tokens in/out, latency, answer accuracy (LLM judge, prompt in repo)
- [ ] `ragtrail eval --dataset wixqa --n 200` → markdown report in `reports/`

**Accept:** reproducible report; accuracy delta warm−cold reported with confidence interval, not just the mean.

## M6 — AWS target (self-contained)
- [ ] `ragtrail[aws]`: `DynamoStore` (single table, provisioned capacity, native TTL on `expires_at`)
- [ ] `deploy/aws/`: SAM template — HTTP API + Lambda (`recall`, `record`) + DynamoDB; billing alarm included
- [ ] Fake-backed unit tests; integration test behind `RAGTRAIL_IT=1`
- [ ] `docs/deploy-aws.md`: free-tier limits re-verified on the deploy date

**Accept:** `sam deploy` from a clean account; recall/record over HTTP; teardown documented.

## M7 — Azure target (self-contained)
- [ ] `ragtrail[azure]`: `CosmosStore` (free-tier account, container TTL)
- [ ] `deploy/azure/`: Bicep — Functions (Consumption) + Cosmos DB; budget alert included
- [ ] Same test strategy as M6; `docs/deploy-azure.md`

**Accept:** `az deployment` from a clean subscription; same HTTP contract as AWS.

## M8 — Release
- [ ] README: problem, 30-second demo, eval table, honest limitations, relation to subforest
- [ ] `v0.1.0` on PyPI, GitHub release, tag

## Later (not MVP)
- Optional embedding matcher for far paraphrases (`ragtrail[embed]`)
- Consume change events from an incremental indexer to invalidate proactively instead of on read
- Trail analytics: most reused nodes, dead trails, hit rate per scope
- Thin TypeScript client over the HTTP/MCP contract (`ragtrail` on npm)
