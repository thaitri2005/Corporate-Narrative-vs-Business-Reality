# STRUX Consumer Staples coverage audit

> Status: Stage 1 acquisition/structural screen complete  
> Dataset revision: `8c3d39f2d70a8fa2d619f8c7bef9176efcb89520`  
> Audit date: 2026-09-05

## Result

The pinned STRUX `full` split contains 549 calls for all 34 securities in the point-in-time Consumer
Staples universe. The filtered Parquet is 8,884,666 bytes (~8.47 MiB), derived from 295,339,860
verified raw bytes (~281.7 MiB). No duplicate ticker/date rows or blank speech segments were found.

The corpus contains approximately 5.17 million whitespace-delimited words. Median call length is
9,425 words (range 3,867–30,920). This is small enough for local CPU preprocessing; embedding/model
choices remain subject to the later benchmark gate.

## Coverage constraint

Company call counts range from 5 to 27 (median 15). At the predeclared minimum of 12 calls, 28 of 34
companies qualify. However, temporal endpoints are uneven:

| Last observed call year | Companies |
|---:|---:|
| 2021 | 15 |
| 2022 | 5 |
| 2024 | 14 |

Only 12 companies both meet the 12-call threshold and have a call in 2024. Therefore, the project
must not describe STRUX as a balanced 2017–2024 panel. The feasible choices at the cohort gate are:

1. Use an unbalanced panel with explicit year/firm coverage rules and sensitivity checks.
2. Shorten the common study window, sacrificing recent years for a larger cohort.
3. Select a smaller recent-coverage cohort.
4. Add a replacement/supplemental transcript adapter for missing late years.

No choice is made by this acquisition audit. Selection must occur before outcome-association work
and must not be tuned using financial results.

## Reproduction and interpretation

`cnbr transcript-audit --config configs/data/audit.yaml` generates a call-level structural
table, company-level coverage table, and hash-bound JSON manifest. Outputs contain counts and dates,
not transcript text, and remain DVC-managed pending release review.

This audit establishes acquisition integrity and coarse structural completeness only. It does not
yet prove fiscal-quarter alignment, correct speaker-role semantics, call completeness, or absence of
selection bias.

## Canonical normalization result

The deterministic normalization stage produced 549 calls, 7,714 participant records, and 79,467
source-segment utterances. It assigned 54,297 utterances to executives, 17,261 to analysts, 7,241 to
operators, and retained 668 as unknown. Source participant lists omitted speakers in many calls, so
589 flagged observed-speaker participant records were added to preserve referential integrity.

Quality flags identify 457 repeated utterances of at least 20 words, 98 possible source footers, 197
inaudible markers, and 3,875 very short segments. These records are flagged rather than deleted.
Fiscal mapping remains explicitly pending.

For the five-company aligned thin slice, a structural baseline aggregates 983,194 eligible words
across 101 retained company-quarter calls. It excludes 14 source-footer/blank utterances under a versioned
rule and records management-prepared, management-Q&A, analyst-prepared, analyst-Q&A, operator, and
unknown word counts/shares. These are non-semantic diagnostic features, not topic signals.
