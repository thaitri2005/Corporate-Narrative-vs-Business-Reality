# Data and compute capacity estimate

> Estimate date: 2026-09-05  
> Status: Planning estimate; replace assumptions with measured Stage 1 values  
> Scope: Text-only Consumer Staples study, 34-company sampling frame and approximately 180–600
> usable company-quarter calls after coverage exclusions

## 1. Known reference points

- The [STRUX project](https://struxdata.github.io/) describes 11,950 transcripts from 869 companies with an average of approximately 10,187 tokens per transcript.
- The current [Hugging Face dataset page](https://huggingface.co/datasets/BUILDERlym/STRUX-Transcripts) reports approximately 343 MB of downloadable/auto-converted Parquet files and 13,098 rows across its published splits. Some splits may overlap, so split sizes must not be summed as unique calls without inspection.
- The repository's current base `.venv` is approximately 344 MiB. The uv download/build cache is approximately 429 MiB after resolving base and optional DVC packages; it is disposable and can be cleaned/recreated.

## 2. Expected target-study text volume

| Scenario | Calls | Tokens at 10,187/call | Approximate words | Raw/Parquet transcript slice |
|---|---:|---:|---:|---:|
| Minimum viable | 180 | 1.83 million | 1.35–1.55 million | 5–15 MB |
| Expected | 350 | 3.57 million | 2.6–3.0 million | 10–30 MB |
| Upper target | 600 | 6.11 million | 4.5–5.2 million | 18–50 MB |
| Full STRUX reference | 11,950 | 121.7 million | 90–105 million | 343 MB download; roughly 0.7 GB materialized reference |

The subset estimate is wider than simple proportional scaling because Parquet compression and nested-list overhead behave differently after filtering and normalization.

The accepted 2026-09-05 universe snapshot contains 34 Consumer Staples securities/unique CIKs. Its
curated Parquet is only 6,619 bytes, confirming that reference data is negligible. Even a theoretical
34 companies × 32 quarters is 1,088 calls; real usable coverage will be lower. The existing 2–5 GB
ordinary working-storage estimate remains conservative and appropriate.

## 3. Derived NLP volume

Assuming approximately 256 tokens per model chunk before overlap:

| Scenario | Base chunks | With 10–20% overlap/segmentation overhead |
|---|---:|---:|
| 180 calls | ~7,200 | ~8,000–9,000 |
| 350 calls | ~14,000 | ~15,500–17,000 |
| 600 calls | ~24,000 | ~26,000–29,000 |

Embedding storage in float32:

| Embedding width | 9k chunks | 17k chunks | 29k chunks |
|---|---:|---:|---:|
| 384 dimensions | ~14 MB | ~26 MB | ~45 MB |
| 768 dimensions | ~28 MB | ~52 MB | ~89 MB |

Metadata, Parquet encoding, multiple section views, and alternate model versions can multiply these figures. A practical feature/embedding allowance is **0.1–1 GB** for the target cohort.

## 4. Financial data

For the 34-company sampling frame, selected SEC submissions and Company Facts JSON plus normalized Parquet tables should usually remain below **0.1–1 GB**. The uncertainty comes from retaining full company histories, filing versions, and source documents. Bulk all-company SEC archives are unnecessary for v1 and would increase storage by many gigabytes.

Measured Stage 1 evidence: submissions, required history shards, and Company Facts for five
deliberately varied companies occupy 21,842,180 bytes (~20.8 MiB). Linear extrapolation to all 34
candidates is approximately 149 MB before filesystem/versioning overhead. A 0.25–0.5 GB raw SEC allowance is therefore practical;
the broader 0.1–1 GB planning range remains conservative.

Company presentations or PDF filings can dominate the financial footprint if downloaded indiscriminately. Store only source documents required for governed Tier C metrics and preserve locators/checksums where rights permit.

## 5. Model and experiment storage

| Component | Planning allowance |
|---|---:|
| Small sentence-embedding model | 0.1–0.8 GB |
| Finance/BERT-class encoder | 0.4–1.5 GB |
| Tokenized/cached target corpus | 0.1–1 GB |
| One fine-tuning checkpoint including optimizer state | 2–8 GB |
| Several candidate/checkpoint runs | 10–40 GB |
| Classical TF-IDF/model artifacts | Usually below 1 GB |

Checkpoint retention, rather than the research tables, is likely to be the largest controllable storage cost.

## 6. End-to-end disk budget

| Working mode | Expected active footprint | Recommended free disk |
|---|---:|---:|
| Classical NLP, target cohort only | 2–6 GB | 15 GB |
| Embeddings and several local models | 8–20 GB | 40 GB |
| Transformer fine-tuning/checkpoint experimentation | 20–60 GB | 100 GB |
| Full STRUX retained plus multiple DVC versions/models | 30–80 GB | 100–150 GB |

These totals include environment/model caches, raw/interim/curated/feature layers, DVC's content cache, and operating headroom. DVC may roughly duplicate versioned artifacts locally when hardlink/reflink optimization is unavailable. Do not reserve distributed-storage infrastructure for this scale.

**Recommendation:** keep at least **50 GB free** for the expected study. Reserve **100 GB** if local transformer fine-tuning or many model checkpoints are likely.

## 7. Memory and compute

- **RAM:** 16 GB minimum; **32 GB recommended**. Polars/DuckDB can handle this corpus comfortably with lazy scans and Parquet. 64 GB is not justified by current scope.
- **CPU:** A modern 6–12 core workstation is sufficient for ingestion, classical NLP, embeddings, and panel analysis. Full target-cohort CPU embedding inference should be hours rather than days, but Stage 4 benchmarks will replace this estimate.
- **GPU:** Not required for Stage 1–3 or classical baselines. For BERT-class fine-tuning, 8 GB VRAM is a constrained minimum; **12–16 GB VRAM** is more comfortable with mixed precision and modest batches. Renting short batch jobs is preferable to purchasing hardware before the model-adoption gate.
- **Network:** Initial STRUX download is roughly 343 MB according to the current dataset page. Model downloads are commonly 0.1–2 GB each. SEC requests should be cached and rate-policy compliant.

## 8. Annotation workload

Data size is small; human review is heavier than storage. A 1,500–4,000 chunk labeled set with overlap for double annotation is a plausible starting range. At roughly 30–75 seconds per chunk including decisions, annotation represents approximately 20–85 first-pass hours before training, adjudication, and codebook revision. The taxonomy pilot must measure actual throughput.

## 9. Capacity controls

- After explicit permission/license is retained, download STRUX once, filter locally, and verify
  duplicate split semantics. Until then, do not acquire transcript content.
- Store durable tables as compressed Parquet.
- Reuse one frozen embedding artifact across model comparisons when valid.
- Retain best/final checkpoints and evaluation artifacts; delete redundant recoverable checkpoints under a documented policy.
- Keep uv/Hugging Face caches outside DVC.
- Avoid bulk SEC archives and unnecessary PDFs.
- Measure row count, token count, chunk count, bytes, and stage runtime in Stage 1.
- Revise this estimate after real Consumer Staples filtering and a three-company pipeline benchmark.
