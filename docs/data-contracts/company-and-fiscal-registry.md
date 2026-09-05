# Company and fiscal registry contract

> Schema version: 2.0
> Implementation: `src/cnbr/contracts/registry.py`

## Purpose

These contracts form the identity and time spine for every later join. They are deliberately
provider-neutral and distinguish effective identifiers, fiscal reporting periods, earnings calls,
release timestamps, and filing availability.

## Company identifier

Grain: one identifier value over one effective interval.

```text
schema_version
company_id
identifier_type: cik | ticker | legal_name | provider_id
identifier_value
valid_from, valid_to
source_id
overlap_exception_reason
```

`company_id` is the durable internal key. Ticker and legal name are attributes, never keys.
Intervals are inclusive. Open-ended `valid_to` means still active. Two values of the same identifier
type may not overlap for one company unless both rows carry an explicit reviewed exception.

## Fiscal period

Grain and key: `(company_id, fiscal_year, fiscal_quarter)`.

```text
schema_version
company_id, fiscal_year, fiscal_quarter
period_start, period_end
earnings_release_at
call_id, call_date, call_started_at, call_time_precision
filing_accepted_at
mapping_source
mapping_exception_reason
```

Missing calls remain null rather than manufacturing an observation. A mapped call always has
`call_date`; `call_started_at` exists only when the source provides a timezone-aware timestamp.
`call_time_precision` makes that distinction explicit. A call maps to at most one quarter. A call dated before period end is rejected
unless a reviewed mapping exception explains the source anomaly. Periods for the same company may
not overlap; non-calendar fiscal years are fully supported.

## Boundary checks

- Reject unknown fields and malformed/negative intervals.
- Reject duplicate canonical quarter keys.
- Reject a call reused across quarters.
- Reject overlapping periods per company.
- Reject overlapping effective identifiers without paired exception reasons.
- Preserve timezone-aware source timestamps when present; naive source timestamps require an
  explicit source normalization rule before materialization.

The Pydantic record models validate type and row invariants. Cross-row functions validate temporal
and referential rules before data is written to a curated Parquet contract.
