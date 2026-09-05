# ADR-009: Preserve date-only call-time precision

> Status: Accepted  
> Date: 2026-09-05

## Context and decision

STRUX supplies a call date but no reliable call start time or timezone. Creating a noon-UTC value
would add false precision and could mislead point-in-time joins. Registry schema 2.0 therefore adds
`call_date` and `call_time_precision` (`date` or `datetime`). A date-precision call must have no
`call_started_at`; a datetime-precision call requires a timezone-aware timestamp whose date agrees.

Fiscal mapping compares `call_date` to `period_end`. Filing acceptance remains a distinct timestamp
and is never treated as the call time. This is a breaking contract change from schema 1.0, made
before production fiscal-period artifacts exist.

## Consequences

Downstream daily joins can use the known date, while intraday sequencing stays unavailable rather
than fabricated. A better authorized source may later populate actual timestamps without changing
the meaning of existing date-precision rows.
