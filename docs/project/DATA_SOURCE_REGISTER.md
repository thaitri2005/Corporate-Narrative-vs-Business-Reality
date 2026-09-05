# Data source register

> Status: Stage 1 working document  
> Updated: 2026-09-05

No source may move from `candidate` to `approved` until acquisition, storage, transformation, external-processing, retention, and release rights are recorded.

| ID | Source | Intended use | Access | License/terms status | Data class | Current decision |
|---|---|---|---|---|---|---|
| SRC-001 | STRUX Transcripts on Hugging Face | Prepared remarks, Q&A, participants, dates | Public download | No explicit dataset license found; upstream text attributed to Motley Fool; owner accepted risk only for private/local personal portfolio analysis | Restricted local | Approved with constraints: pinned/checksummed acquisition; no external API, raw/reconstructable release, or license claim |
| SRC-002 | STRUX project site/paper | Corpus documentation, counts, methodology | Public web/paper | Publication citation applies; not evidence of transcript redistribution rights | Public metadata | Approved for documentation |
| SRC-003 | SEC EDGAR submissions API | Filing history, accepted timestamps, accession records | Public API, no key | SEC automated-access and privacy/security policies apply | Public source data | Approved for feasibility ingestion; proposed primary source |
| SRC-004 | SEC Company Facts/XBRL API | Quarterly standardized financial facts | Public API, no key | SEC automated-access and privacy/security policies apply | Public source data | Approved for feasibility ingestion; proposed primary source pending concept audit |
| SRC-005 | Company filings/investor relations | Verify mappings; narrow operating metrics | Public company sites/EDGAR | Per-site/document terms; retain source locator | Public or source-restricted | Candidate per metric |
| SRC-006 | `datasets/s-and-p-500-companies` Data Package | Point-in-time S&P 500 membership, GICS classification, ticker and CIK | Public GitHub CSV | Data Package declares ODC-PDDL-1.0; upstream attributes Wikipedia | Public metadata | Approved for point-in-time universe snapshots; pin revision and SHA-256 |

The initial SRC-006 snapshot is pinned to Git commit
`3b2bb60e6269439cd75541eded6281c48e7681d1` with snapshot date `2026-09-05`.
The raw SHA-256 is `e06b473e4679074b2aaa49da67dfc154338b466ca66102935d93486c34e16883`;
34 Consumer Staples rows/unique CIKs were retained. The generated manifest is authoritative for
machine execution.

## SRC-001 observed schema

The currently published STRUX Parquet card exposes:

```text
ticker: string
date: string
participants: list[{description, name, position}]
prepared_remarks: list[{name, speech: list[string]}]
questions_and_answers: list[{name, speech: list[string]}]
```

Published split metadata reports:

| Split | Rows | Materialized bytes reported |
|---|---:|---:|
| `train` | 1,100 | 62,622,509 |
| `test` | 587 | 30,994,681 |
| `full` | 11,411 | 588,031,777 |

The combined published download is approximately 343 MB. Train/test appear to be selected evaluation subsets alongside the full corpus; overlap must be tested before using any split counts as unique calls.

The implemented acquisition uses only the two `full` shards at upstream revision
`8c3d39f2d70a8fa2d619f8c7bef9176efcb89520` (approximately 295 MB on the repository file page),
verifies their published SHA-256 values, and filters them locally. It intentionally does not
download the overlapping `train` and `test` views.

The verified raw files total 295,339,860 bytes (~281.7 MiB). Local universe filtering retains 549
calls and all 34 Consumer Staples tickers in an 8,884,666-byte (~8.47 MiB) Parquet. There are no
duplicate ticker/date rows; 28 companies have at least 12 calls. These are acquisition-level checks,
not yet proof of fiscal alignment or transcript semantic quality.

### SRC-001 approved controls

- Purpose is limited to the owner's private personal/CV portfolio analysis.
- Raw source and filtered transcript rows remain ignored by Git and locally DVC-managed.
- No transcript content is sent to third-party APIs or cloud processing services.
- No raw, excerpted, row-level, or reconstructable transcript data is published.
- Public outputs are limited to code, attribution/provenance, methods, and non-reconstructable aggregates.
- The absent license remains an open risk; expanded/team/commercial use requires a new decision.

## SRC-003/004 implemented controls

- Project-owner approval recorded before live API use.
- Identifying User-Agent supplied only at runtime and rejected if absent/placeholder.
- Maximum three workers and process-wide 8 request starts/second.
- Bounded retries for 429/5xx responses with exponential/`Retry-After` backoff.
- JSON-object validation, same-directory atomic replacement, SHA-256, partial-failure manifest, and
  valid-file resume behavior.
- Five-company spike completed with 13/13 artifacts and 21,842,180 bytes: ten main endpoint
  responses plus three provider-declared submission-history shards overlapping 2017–2024.

## Approval checklist

- [ ] Named owner/provider.
- [ ] Stable source URL and immutable revision/snapshot method.
- [ ] Acquisition permitted.
- [ ] Local/team storage permitted.
- [ ] Transformations and model training permitted.
- [ ] External model/API processing permitted or prohibited explicitly.
- [ ] Raw and derived redistribution rights known.
- [ ] Attribution requirements recorded.
- [ ] Retention/deletion obligations recorded.
- [ ] Sensitive/restricted fields classified.
- [ ] Technical access policy and rate limits implemented.
- [ ] Fallback/exit procedure documented.

## References

- STRUX project: <https://struxdata.github.io/>
- STRUX dataset: <https://huggingface.co/datasets/BUILDERlym/STRUX-Transcripts>
- SEC EDGAR APIs: <https://www.sec.gov/search-filings/edgar-application-programming-interfaces>
- S&P 500 Data Package: <https://github.com/datasets/s-and-p-500-companies>
- ODC PDDL 1.0: <https://opendatacommons.org/licenses/pddl/1-0/>
