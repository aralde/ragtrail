# Paper plan

Working title: *Cache the path, not the answer: validated retrieval-path reuse for agentic RAG.*

## Claims

1. Reusing the retrieval path of an earlier, approved answer cuts an agentic RAG agent's tool calls and input tokens
   on repeated questions without lowering judged accuracy.
2. Admission is what makes it safe: unfiltered self-recorded paths replay wrong answers (50% → 21% on questions
   whose first answer was wrong); a gate removes that harm.
3. Storing hash-validated pointers instead of copied evidence means a changed source is never served from cache,
   at a measured cost in lost hits.
4. All of it runs on key reads (LSH bands for both MinHash and embedding SimHash), so it fits any key-value store.

Not claimed: the fixed-context effect (a usage issue, kept in the docs only).

## Experiments

| ID | Experiment | Status | Size |
|---|---|---|---|
| E0 | Oracle trails, WixQA and QASPER (per-hit upper bound) | done | 200 + 400 pairs |
| E1 | Self-recorded, no gate | done | 200 pairs |
| E2 | Self-recorded, ideal gate (judge with reference) | done | 200 pairs |
| E3 | Self-recorded, reference-free gate (`repeat-verified`) | code ready | 200 verifier checks, 200 warm runs |
| E4 | Corpus edits: ragtrail vs copy cache vs unvalidated pointers | done (offline) | 179 + 274 hits × 5 rates |
| E5 | Mixed traffic, empty cache, 10–40% repeats | done (offline) | 444–1,600 questions |
| E6 | Self-recorded + reference-free gate on QASPER (paper as scope) | todo | 400 phase A, 400 checks, 400 warm |
| E7 | Second agent model on E3 | todo | 400 phase A + 200 warm + 200 cold |
| E8 | Judge validation: 150–200 human labels, second judge | todo | labels by hand |
| E9 | Baseline: Agentic Plan Caching on QASPER | todo | 400 |
| E10 | Repeat runs of E3 for run-to-run variance | todo | 2 × 200 |

Order: E3 → E6 → E8 → E7 → E10 → E9. E3 decides the headline: if a reference-free gate keeps accuracy at or above
the cold arm, that is the main result; if not, the paper argues for explicit user feedback as the admission signal.

## Where runs happen

Agent, verifier and judge runs go to a Claude Code cloud session (cloud session credits), not the Pro subscription.
The session clones this repo and subforest, restores the eval data bundle (paraphrases, phase-A runs, cold runs and
judgments are not reproducible bit-for-bit, so they are shipped, not regenerated), rebuilds the corpora with
`ragtrail eval fetch`, and runs the commands below. Results come back as a PR with updated `reports/`.

```bash
ragtrail eval --dataset wixqa verify --embed                         # E3 gate, 200 checks
ragtrail eval --dataset wixqa offline --scenario repeat-verified --embed
ragtrail eval --dataset wixqa agent --scenario repeat-verified --embed --n 200
ragtrail eval --dataset wixqa judge --scenario repeat-verified --embed --model sonnet
ragtrail eval --dataset wixqa report
```
