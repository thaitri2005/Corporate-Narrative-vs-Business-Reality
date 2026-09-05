# ADR-003: Use a provider hierarchy with STRUX provisional and SEC primary

- Status: Proposed; requires Stage 1 evidence
- Date: 2026-09-05
- Owners: Research lead / data steward
- Related design: `PROJECT_DESIGN.md`, Sections 2 and 8

## Context

The brief proposes STRUX for structured calls and requires quarterly financial facts plus selected operating metrics. Transcript rights, coverage, role quality, XBRL comparability, and operating-metric availability are not yet proven.

## Decision drivers

- Lawful storage, transformation, model processing, and release.
- Company-quarter coverage and role/section fidelity.
- Primary-source provenance and point-in-time timestamps.
- Replaceability if a source fails.

## Considered options

- STRUX plus SEC EDGAR/XBRL and company filings.
- A licensed combined transcript/financial provider.
- Manually assembled investor-relations material.
- A newly built broad SEC corpus.

## Proposed decision

Treat STRUX as a candidate, not a commitment. Use SEC EDGAR submissions/XBRL as the primary standardized financial source, company filings for verification/operating metrics, and licensed sources only through explicit adapters.

## Consequences

Stage 1 begins with rights and coverage diligence. Providers remain separate, records retain provenance, and public release may contain only permitted schemas, synthetic fixtures, and aggregates.

## Validation and rollback

Accept only if Stage 1 license, coverage, role-quality, fiscal-mapping, and financial-concept audits pass. Otherwise switch the affected adapter or revise scope through another ADR.
