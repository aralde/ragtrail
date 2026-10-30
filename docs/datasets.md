# Datasets

Checked before downloading. Data is never committed: `ragtrail eval fetch` downloads into `$RAGTRAIL_DATA`
(default `~/.cache/ragtrail/datasets`) and builds `corpus.db` and `questions-<split>.jsonl` there.

| Dataset | Source | License | Used for | Size |
|---|---|---|---|---|
| WixQA: KB corpus + ExpertWritten, Simulated, Synthetic splits | [Wix/WixQA](https://huggingface.co/datasets/Wix/WixQA) | MIT | M5 cold vs warm | 6,221 articles; 200 + 200 + 6,221 questions |

License checked on 2026-10-30 from the dataset card's `license` field (`mit`).

## Notes

- The KB is built into a subforest corpus with subforest's own WixQA builder (article type → product → article,
  sections from the article HTML). Gold = each question's `article_ids` mapped to document nodes (`n123`).
- **Disjoint scenario**: warm-up = Simulated + Synthetic, test = ExpertWritten. No exact normalized duplicates
  between them (checked by `ragtrail eval offline`, reported as "exact normalized duplicates").
- **Repeat scenario**: `ragtrail eval paraphrase` writes one paraphrase per ExpertWritten question with a small
  model through `claude -p` (`questions-paraphrase.jsonl`, also not committed). Warm-up = the originals,
  test = the paraphrases. Overlap is the point of this scenario, so it is reported separately.
