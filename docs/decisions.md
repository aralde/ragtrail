# Decisions

One line per decision: date — decision — reason.

- 2026-10-29 — `ragtrail` is free on PyPI (checked 2026-10-29) — keep the name.
- 2026-10-29 — Models are frozen pydantic models with `extra="forbid"` — immutable values are safe to share, and an accidental `answer` field fails loudly.
- 2026-10-29 — `Trajectory` gains `stale: bool = False`; `id` defaults to a uuid4 hex — `mark_stale` needs a representation; ids are generated where trajectories are built.
- 2026-10-29 — `scope` and `id` must be non-empty and must not contain `#`; datetimes must be timezone-aware and `expires_at > created_at` — `#` is the key separator, so this is what keeps scopes from colliding.
- 2026-10-29 — `put(trajectory, band_keys)` takes full band keys from the caller; the store checks each one is a band key of the trajectory's scope — the store stays independent of `MatchConfig`, and scope isolation is enforced at the storage boundary.
- 2026-10-29 — `candidates` raises `ValueError` on a band key outside `scope` instead of ignoring it — a cross-scope lookup is a caller bug and should be loud.
- 2026-10-29 — Stale trajectories are excluded from `candidates` but still returned by `get` — recall never reuses them, debugging still can see them.
- 2026-10-29 — A trajectory is expired when `expires_at <= now`; `get`, `candidates` and `incr_hits` ignore expired items even before `purge_expired` runs — mirrors DynamoDB/Cosmos, whose native TTL deletes lazily.
- 2026-10-29 — Band buckets keep the newest `band_cap` entries (default 32) by `created_at`; older entries are dropped on `put` — bounded reads per band, matching the capped list item in DynamoDB/Cosmos.
- 2026-10-29 — Stores take an injectable `clock` — TTL tests run without sleeping.
- 2026-10-29 — `SQLiteStore` keeps `hits` and `stale` as columns that override the stored JSON — counters update in place without rewriting the document.
- 2026-10-29 — Store tests are written against the `TrajectoryStore` protocol with a parametrized `store` fixture — cloud backends (M6/M7) reuse the same suite against their fakes.
- 2026-10-29 — Docstring examples run as doctests (`--doctest-modules`) — keeps the "every public function has an example" rule honest.
