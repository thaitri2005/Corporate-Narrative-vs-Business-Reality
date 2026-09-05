# ADR-005: Use a point-in-time S&P 500 Consumer Staples universe

- Status: Accepted
- Date: 2026-09-05
- Owners: Project lead and tech lead

## Context

The project is intentionally limited to one industry. It needs a reproducible definition of
“Consumer Staples,” stable company identifiers for SEC integration, and a cohort small enough for
careful transcript and financial validation. A broad SIC-derived universe would not match the
standard GICS sector. Proprietary historical constituent data would add rights and procurement
work before feasibility is established.

## Decision

Use a point-in-time snapshot of S&P 500 constituents and retain records whose GICS sector label is
exactly `Consumer Staples`. Acquire the CSV from the maintained
`datasets/s-and-p-500-companies` Data Package, whose metadata declares ODC-PDDL-1.0 for the data.
Record the exact upstream revision, retrieval/snapshot date, source and configuration identifiers,
license, raw SHA-256, and row-level fingerprints. Normalize CIK to ten digits and use an internal
CIK-derived identifier at this registry boundary; never use ticker as the durable company key.

Treat the resulting table as a current-membership sampling frame. Apply transcript coverage and
quality criteria only after the universe snapshot is frozen. Do not describe the snapshot as
historical index membership.

## Alternatives considered

- SEC SIC mapping: open and broad, but not equivalent to the GICS Consumer Staples sector and
  requires subjective mapping choices.
- Proprietary historical GICS/index membership: methodologically stronger for historical
  membership, but unnecessary cost and rights complexity before M1.
- Hand-maintained company list: simple but irreproducible and prone to undocumented selection.

## Consequences

- Current-member and survivorship selection limitations must appear in cohort reports and claims.
- Companies absent from the current S&P 500 are outside the initial frame even if they were members
  during 2017–2024.
- The adapter must fail on schema drift, invalid CIKs, duplicate company mappings, or an empty
  sector result.
- A move to historical membership or another industry classification requires a new ADR and cohort
  version; downstream contracts do not need to change.

## Validation and rollback

Validate the source schema, license metadata, content hash, sector row count, CIK uniqueness, and a
manual sample against source records. If the source becomes unavailable or its terms/schema change,
retain the immutable prior snapshot and replace only the registry adapter after rights review.
