# Stage 1 feasibility record

> Status: Started  
> Updated: 2026-09-05  
> Gate: M1 — Feasibility decision

## Objective

Determine whether the intended Consumer Staples study is legally usable, sufficiently covered, temporally alignable, and supported by comparable financial outcomes before production-scale ingestion or modeling.

## Current findings

### Transcript source

- STRUX documents 11,950 calls from 869 companies across 2017–2024, averaging approximately 10,187 tokens per call.
- The currently published Hugging Face repository exposes 13,098 rows across `train`, `test`, and `full`, with a 343 MB download and approximately 682 MB reported materialized size.
- The dataset schema contains ticker/date, participant records, prepared remarks, and Q&A speaker/speech lists.
- No explicit license identifier or usable redistribution terms were found in the current dataset card metadata reviewed on 2026-09-05.
- The card states “More Information needed,” and the project describes Motley Fool as the transcript source.

**Ruling:** on 2026-09-05 the project owner explicitly accepted the unresolved license risk for this
private personal/CV project. Local download and transformation are allowed for the project; raw or
reconstructable text must stay out of Git/public releases and external APIs. This is a project risk
decision, not a claim that a license or redistribution permission exists.

### Financial source

- SEC `data.sec.gov` provides JSON submissions and XBRL Company Facts without authentication keys.
- Filing acceptance timestamps support point-in-time construction.
- Company-specific fiscal calendars and XBRL mappings still require a multi-company spike.
- Automated requests require an identifying user-agent and compliance with SEC access policy.

The project owner approved read-only SEC API use on 2026-09-05 and supplied a monitored contact
email. The runtime identity is not committed. The implemented client uses at most three workers,
limits request starts to 8/second across threads, retries only bounded transient failures, validates
JSON objects, writes atomically, hashes artifacts, and resumes from valid local files.

The five-company spike acquired submissions and Company Facts for KO, PG, COST, WMT, and MO:

| Measure | Result |
|---|---:|
| Companies | 5 |
| Base endpoint artifacts | 10 |
| Overlapping submission-history shards | 3 |
| Successful total | 13 |
| Failed | 0 |
| Raw bytes | 21,842,180 (~20.8 MiB) |
| Workers | 3 maximum |
| Request-start cap | 8/second |

This is an acquisition success, not yet evidence that fiscal-period mappings or concepts are
comparable. That assessment is the next local step.

The main submissions response is a rolling recent window, not necessarily the full study history.
The downloader now discovers provider-declared history shards and acquires only shards whose date
range overlaps 2017–2024. Three shards closed the observed KO, PG, and WMT gaps.

### Filing and acceptance-time spine

Recent and overlapping history submissions normalize to 170 unique 10-K/10-Q accessions across the
five companies, including 10 amendments. Every company has 32 base filings covering the intended
eight fiscal years; KO and PG each add one amendment and MO adds eight. The table preserves report
date, filing date, SEC acceptance timestamp, form/amendment status, primary document, source shard,
CIK, ticker, entity name, and fiscal-year-end metadata. This passes filing availability and
identifier continuity, while fact-to-filing and fiscal-quarter value reconciliation remain open.

### Initial Company Facts availability screen

The local, hash-bound audit counted unique `(fiscal_year, fiscal_period)` labels from 2017–2024 for
candidate US-GAAP concepts. These are availability results only; they do not prove correct duration,
dimensions, amendments, Q4 derivation, or economic comparability.

| Candidate metric | Companies with any coverage | Median label coverage | Initial ruling |
|---|---:|---:|---|
| Revenue family | 5/5 | 100% | Continue to reconciliation |
| Operating income | 5/5 | 100% | Continue; strongest margin numerator candidate |
| Inventory | 5/5 | 100% | Continue; instant-fact timing checks required |
| CapEx | 5/5 | 100% | Continue; derive quarters from YTD only with explicit rules |
| Direct gross profit | 3/5 | 12.5% | Not universal; conditional/derived mapping only |

Direct `GrossProfit` is absent for PG and WMT and appears for only four fiscal labels for COST. The
project must not declare standardized gross margin across the cohort without a validated
revenue-minus-cost derivation and company-level reconciliation. Detailed evidence:
`docs/project/SEC_CONCEPT_COVERAGE.md`.

### Capacity

- No big-data infrastructure is justified.
- The two verified `full` shards total 295,339,860 bytes (~281.7 MiB); the locally filtered
  Consumer Staples Parquet is 8,884,666 bytes (~8.47 MiB).
- The filtered data contains 549 calls across all 34 universe tickers, with zero duplicate
  ticker/date rows and no empty participant, prepared-remarks, or Q&A lists.
- Company coverage ranges from 5 to 27 calls (median 15); 28 companies have at least 12 calls and
  17 have at least 16. The target cohort is therefore feasible, subject to fiscal and content QA.
- Coverage is temporally uneven: 15 companies end in 2021, five in 2022, and 14 reach 2024. Only 12
  both meet the 12-call threshold and reach 2024. A balanced 2017–2024 panel is not supported as-is;
  the cohort/window/supplemental-source choice remains open until the coverage gate.
- The corpus contains approximately 5.17 million whitespace-delimited words (median 9,425 per call),
  confirming that local CPU preprocessing is viable.
- Total ordinary working storage remains approximately 2–5 GB before transformer checkpoints.
- Detailed estimate: `docs/project/CAPACITY_ESTIMATE.md`.
- Transcript audit: `docs/project/STRUX_COVERAGE.md`.
- Canonical normalization now preserves all 79,467 source speech segments across 549 calls with
  deterministic identifiers, source coordinates, role/section labels, text hashes, and quality
  flags. It creates flagged observed-speaker records where source participant lists are incomplete;
  no transcript text enters manifests, logs, tests, or public reports.

### Company-universe implementation

- The commit-pinned 2026-09-05 source snapshot contains **34** Consumer Staples securities and 34
  unique CIKs after strict sector filtering.
- Raw CSV SHA-256:
  `e06b473e4679074b2aaa49da67dfc154338b466ca66102935d93486c34e16883`.
- The curated Parquet is 6,619 bytes; the universe itself is operationally negligible compared with
  transcript text, model artifacts, and versioned intermediate datasets.
- The adapter fails closed on schema drift, invalid/duplicate CIKs, or an empty sector result and
  stores normalized ten-digit CIKs, source revision, row fingerprints, and a lineage manifest.
- Coverage and quality rules will reduce 34 candidates to the final analytical cohort; the earlier
  15–30 figure is a target cohort size, not a hand-selected universe cap.

### Identity and fiscal contract implementation

- Registry schema v1.0 now defines effective-dated CIK, ticker, legal-name, and provider identifiers.
- Fiscal-period schema v1.0 separates period, earnings-release, call, and filing-acceptance time.
- Cross-row validation rejects overlapping identifiers/periods, duplicate quarter keys, and one
  call mapped to multiple quarters; explicit reviewed exceptions remain possible where designed.
- Unit fixtures cover ticker change, non-calendar periods, missing calls, and invalid mappings.

## Decisions

### DEC-S1-01 — STRUX rights path

**Accepted 2026-09-05, superseding the earlier permission-first choice:** use STRUX for private,
local portfolio research under explicit owner risk acceptance. Do not send text to external APIs or
release raw, excerpted, row-level, or otherwise reconstructable transcript content. Publish only
pipeline code, source attribution/provenance, methodology, and non-reconstructable aggregates. A
licensed replacement or written permission is required before broader use.

Alternatives:

1. Obtain explicit permission/license and retain STRUX.
2. Use STRUX only for private local research after owner/legal risk acceptance, with no raw-text redistribution or external API processing.
3. Replace STRUX with a clearly licensed transcript source.

### DEC-S1-02 — Consumer Staples universe

**Accepted 2026-09-05:** define the initial universe from a point-in-time S&P 500 constituent
snapshot, retaining rows whose GICS sector is exactly `Consumer Staples`. Use the maintained
`datasets/s-and-p-500-companies` Data Package, which declares ODC-PDDL-1.0 for its data and includes
ticker and CIK. Pin each acquisition by upstream revision and content hash. Disclose that this is
current membership and therefore creates survivorship/current-constituent selection limitations
when analyzing 2017–2024 calls.

Alternative: derive an industry universe from public SEC SIC codes. This avoids dependence on a GICS snapshot but does not correspond exactly to the standard Consumer Staples sector and needs a documented code mapping.

### DEC-S1-03 — SEC request identity

**Accepted 2026-09-05:** the project owner supplied a monitored contact email and approved read-only
SEC API use. The identifying User-Agent is supplied at runtime and is not committed. The adapter
rejects missing/placeholder identities; the five-company live acquisition completed within the
three-worker and 8-request-starts/second limits.

## Work proceeding under the accepted controls

- Extend the implemented/tested SEC adapter into cached, rate-controlled acquisition.
- Extend the implemented universe registry into effective-dated identity and fiscal-period contracts.
- Create coverage-report schemas and commands.
- Acquire the two pinned STRUX `full` shards, verify hashes, and filter locally.
- Develop the literature/construct evidence matrix.

## Gate evidence remaining

- STRUX restricted-use decision and machine-enforced local acquisition path.
- Versioned Consumer Staples universe artifact and manifest.
- Detailed STRUX fiscal-quarter mapping and content-quality matrix (basic coverage passed: 549 calls,
  34/34 tickers, 28 with at least 12 calls).
- Multi-company SEC concept/period reconciliation.
- Candidate primary-mechanism coverage scorecard.
- Revised effort and risk estimate.
- Formal Go / Go with constraints / Pivot / Stop decision.
