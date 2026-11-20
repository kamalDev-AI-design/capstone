# Evaluation (measured locally - nothing here is a published benchmark)

`python eval/run_eval.py --profile fast [--threshold 0.4] [--calibrate]` seeds a temporary DB (36 fictional reports,
7 SOP files incl. a superseded version), builds the real index with the chosen models, then runs ~105 synthetic queries
(exact REF/LOT, paraphrase/synonym, SOP questions, status/date filters, mixed SOP+report, unanswerable, prohibited).
Ground truth is derived from the seeded text (`eval/gold.py`), so reference IDs never drift. Raw output: `eval/results/*.json`.

## Run recorded on this machine - profile `fast` (BAAI/bge-small-en-v1.5 + cross-encoder/ms-marco-MiniLM-L-6-v2), CPU, 2026-11-05

| Metric | Result @ rerank threshold 0.40 | Project target | Met? |
|---|---|---|---|
| Exact reference lookup (top-1) | 1.00 | 1.00 | yes |
| Exact lot lookup (all cited relevant) | 1.00 | 1.00 | yes |
| Recall@20 | 0.970 | >= 0.95 | yes |
| nDCG@10 | 0.954 | >= 0.85 | yes |
| MRR@10 | 0.966 | - | - |
| Citation precision | 0.988 | >= 0.98 | yes |
| Correct abstention (unanswerable) | 1.00 | >= 0.95 | yes |
| Prohibited-request blocking | 1.00 | 1.00 | yes |
| Stale SOP returned by default | 0 | 0 | yes |
| Repeated invalid tool call blocking | 1.00 | 1.00 | yes |
| **False abstention on answerable queries** | **0.272** | (not a stated target) | **weak** |
| **Mixed SOP+report returns both source types** | **0.143** | (not a stated target) | **weak** |
| p95 retrieval latency | ~489 ms | - | - |
| p95 end-to-end (agent) latency | ~496 ms | - | - |

## Threshold trade-off (same queries)
| Rerank threshold | Citation precision | False abstention | Mixed both-types |
|---|---|---|---|
| 0.40 (default) | 0.988 | 0.272 | 0.143 |
| 0.01 | 0.934 | 0.136 | 0.429 |
| 0.002 | 0.922 | 0.099 | 0.429 |

## Interpretation
- Retrieval ranking is strong; the weakness is the **small MS-MARCO reranker's relevance scores**: true paraphrase matches often score
  near zero, so no single threshold meets every target. Lowering it improves recall of answers but admits marginal citations.
- A dense-cosine second gate was tried in calibration and gave only a marginal gain, so it was **not** added.
- The default stays at 0.40 (abstaining is the safer failure mode). The `full` profile (BGE-M3 + BGE-Reranker-v2-M3) has **not been
  evaluated**: the reranker download failed because the disk was full. Re-run this script with `--profile full` after freeing ~3 GB.
- Gold set is small (105 queries, 36 reports, 12 unanswerable); treat calibration conclusions as indicative, not definitive.
