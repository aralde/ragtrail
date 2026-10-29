# ragtrail

**Reuse the retrieval paths your agent already solved.**

`ragtrail` is a trajectory cache for agentic RAG. When an agent answers a question, ragtrail records the *path* it
took — which searches it ran, which nodes (sections, chunks, docs) it opened, and which of them ended up cited. When a
similar question arrives, ragtrail hands that path back so the agent skips the orientation phase: from 5–8 tool calls
to 1–2. Paths are invalidated by content hash when the underlying nodes change.

MIT-licensed. Sibling project of `subforest` (aralde/subforest), but **index-agnostic**: works with subforest node ids
or with plain chunk/doc ids from any RAG stack.

## Why this exists (keep every decision aligned to this)
- Agentic RAG pays a per-query orientation cost (several search/expand/read calls) even when an almost identical
  question was resolved yesterday.
- Answer caches are dangerous in RAG: answers go stale and can leak across permission boundaries.
- Caching the **path, not the answer**, keeps generation fresh while cutting tool calls, tokens and latency.
- The headline claim to prove: warm cache cuts tool calls and tokens **without lowering answer accuracy**.

## Product shape
1. `ragtrail.models` — `Trajectory`, `Step`, `NodeRef`, `RecallResult` (pydantic).
2. `ragtrail.normalize` + `ragtrail.match` — query normalization and MinHash signatures with LSH banding.
   Pure stdlib, deterministic (fixed seeds). Each band becomes a store key, so lookup is key reads, no vector DB.
3. `ragtrail.store` — `TrajectoryStore` protocol. `SQLiteStore` in core; `DynamoStore` (`ragtrail[aws]`) and
   `CosmosStore` (`ragtrail[azure]`) as extras.
4. `ragtrail.resolver` — `NodeResolver` protocol: `content_hash(node_id)` and `read(node_id, max_tokens)`.
   `GenericResolver` (callables) in core; `SubforestResolver` in `ragtrail[subforest]`.
5. `ragtrail.recorder` — collects steps during an agent turn, applies the admission policy, writes the trajectory.
6. `ragtrail.recall` — match → validate hashes → decide mode (`prefetch` | `hint` | `miss`) → render within budget.
7. `ragtrail.mcp` — MCP server (`ragtrail[mcp]`) exposing `recall` and `record`; plus a framework-agnostic
   Python middleware (`with ragtrail.turn(...) as t:`).
8. `ragtrail.eval` — cold vs warm harness (`ragtrail[eval]`).
9. `deploy/aws` and `deploy/azure` — separate, self-contained serverless targets. **Never mix clouds in one deploy.**

## Core rules
- **Never store answers.** Only queries, steps, node ids, content hashes and outcome signals.
- **Scope isolation.** Every key starts with `scope` (tenant / permission group). No lookup ever crosses scopes.
- **Admission policy.** A trajectory is written only with a positive signal: verified citations, explicit user
  feedback, or a caller-provided `accepted=True`. No signal → nothing stored.
- **Validation on read.** `prefetch` only if similarity ≥ `prefetch_threshold` AND every useful node's hash matches.
  Some hashes changed → downgrade to `hint` listing only still-valid nodes. All changed → `miss` and mark stale.
- **TTL everywhere.** Every trajectory has `expires_at`; stores must honor it (native TTL on DynamoDB/Cosmos).
- **Budgeted rendering.** `recall` output respects `budget_tokens`; collapse instead of truncating mid-node.

## Stack and conventions
- Python ≥ 3.11, `uv`, `src/` layout, package name `ragtrail`.
- `ruff` (lint + format), `mypy --strict` on `src/`, `pytest`.
- Core has **zero heavy deps**: stdlib + `sqlite3` + `pydantic`. boto3, azure-cosmos, MCP, datasets, LLM SDKs live
  in extras (`ragtrail[aws]`, `[azure]`, `[mcp]`, `[eval]`, `[subforest]`).
- Tests never touch the network or real clouds. Cloud stores are tested against in-memory fakes implementing the
  same protocol; optional integration tests behind `RAGTRAIL_IT=1`.
- Typed public API; every public function has a docstring with a short example.
- Commits: conventional commits (`feat:`, `fix:`, `test:`, `docs:`), small, one concern each.

## Data model (initial — refine in M0, then keep stable)
- `NodeRef(node_id: str, content_hash: str)`
- `Step(tool: str, args: dict, returned: list[str])`
- `Trajectory(id, scope, query, query_norm, signature: list[int], steps: list[Step], useful: list[NodeRef],
   outcome: "verified"|"feedback"|"accepted", created_at, expires_at, hits: int)`
- `RecallResult(mode: "prefetch"|"hint"|"miss", trajectory_id | None, similarity: float,
   nodes: list[NodeRef], stale: list[str], rendered: str)`

## Store key layout (same logic in every backend)
- Trajectory item: `PK = t#{scope}#{trajectory_id}`
- LSH band item: `PK = b#{scope}#{band_idx}#{band_hash}` → list of trajectory ids (capped, newest first)
- Lookup = read the `b` keys for the query's bands, union candidates, compute exact Jaccard on signatures, rank.

## Recall contract (what the agent sees)
```
ragtrail: similar question solved before (similarity 0.82, mode=hint)
  Useful nodes still valid:
    Authentication › Tokens [n33]
    API › Sessions [n58]
  Changed since: Authentication › Refresh [n35] (skipped)
Start with read("n33") before searching.
```
In `prefetch` mode the node contents are included (with breadcrumbs), under the token budget.

## Free tier notes (verify again before each deploy milestone; pricing changes)
- AWS: Lambda 1M requests + 400k GB-s/month always free. DynamoDB always-free covers **provisioned** capacity
  (25 RCU/WCU, 25 GB), not on-demand → the SAM template must use provisioned mode. S3 is not needed.
- Azure: Functions Consumption plan 1M executions + 400k GB-s/month; Cosmos DB free tier (1000 RU/s, 25 GB),
  one free-tier account per subscription.
- Local: SQLite, no cloud.

## Non-goals (MVP)
- No answer caching, no UI, no auth layer (callers pass `scope`; enforcing permissions is the caller's job).
- No embeddings in core (optional extra later for far paraphrases).
- No incremental indexing — that is a separate future project; ragtrail only consumes content hashes.

## How to work in this repo
- Follow `PLAN.md` milestone by milestone; tick checkboxes as you go.
- Small decisions go to `docs/decisions.md`. Stop and ask only for decisions that are hard to reverse and not covered here.
