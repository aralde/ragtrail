# Datasets

Checked before downloading. Data is never committed: `ragtrail eval fetch` downloads into `$RAGTRAIL_DATA`
(default `~/.cache/ragtrail/datasets`) and builds `corpus.db` and `questions-<split>.jsonl` there.

| Dataset | Source | License | Used for | Size |
|---|---|---|---|---|
| WixQA: KB corpus + ExpertWritten, Simulated, Synthetic splits | [Wix/WixQA](https://huggingface.co/datasets/Wix/WixQA) | MIT | M5 cold vs warm | 6,221 articles; 200 + 200 + 6,221 questions |
| QASPER test split v0.3 | [allenai/qasper](https://huggingface.co/datasets/allenai/qasper), archive on `qasper-dataset.s3.us-west-2.amazonaws.com` | CC BY 4.0 | Repeat traffic on long papers | 416 papers; 400 titled questions used (one per paper, with located evidence) |

Licenses checked on 2026-10-30 (WixQA, `mit`) and 2026-10-31 (QASPER, CC BY 4.0, same as subforest's `docs/datasets.md`) from the dataset cards.

## Notes

- The KB is built into a subforest corpus with subforest's own WixQA builder (article type → product → article,
  sections from the article HTML). Gold = each question's `article_ids` mapped to document nodes (`n123`).
- **Disjoint scenario**: warm-up = Simulated + Synthetic, test = ExpertWritten. No exact normalized duplicates
  between them (checked by `ragtrail eval offline`, reported as "exact normalized duplicates").
- **Repeat scenario**: `ragtrail eval paraphrase` writes one paraphrase per ExpertWritten question with a small
  model through `claude -p` (`questions-paraphrase.jsonl`, also not committed). Warm-up = the originals,
  test = the paraphrases. Overlap is the point of this scenario, so it is reported separately.
- **QASPER** reuses subforest's builder and question selection (questions with located evidence, first per paper,
  first 400). Questions are titled (`About "<paper title>": …`), as in subforest's titled mode. Gold = the deepest
  sections holding the evidence spans, which is what a verified answer would cite. Paraphrases keep the title verbatim.
