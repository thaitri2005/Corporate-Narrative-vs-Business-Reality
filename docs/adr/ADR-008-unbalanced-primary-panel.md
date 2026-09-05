# ADR-008: Use a coverage-qualified unbalanced primary panel

> Status: Accepted  
> Date: 2026-09-05

## Context

The pinned STRUX Consumer Staples subset contains 549 calls across all 34 current-universe tickers,
but coverage is not balanced. Twenty-eight companies have at least 12 calls; 15 companies' last
observed call is in 2021, five in 2022, and 14 in 2024. Only 12 companies both meet the 12-call
minimum and reach 2024.

A recent-only cohort would discard useful within-company history and reduce the number of company
clusters. Treating the corpus as balanced would misstate the data and risk selection bias.

## Decision

Use the 28 companies with at least 12 structurally valid, fiscally mapped calls as the candidate
primary cohort. The analytical panel may be unbalanced. Final row eligibility additionally requires
the declared narrative and financial inputs; failures remain explicit rather than imputed silently.

Primary panel models include company and time fixed effects with company-clustered uncertainty.
Predeclare coverage indicators and year/company observation counts. Run at least these sensitivity
checks before interpreting a headline association:

1. the 12-company cohort with at least 12 calls and a call observed in 2024;
2. a common-window or minimum-year-coverage cohort selected without consulting outcomes;
3. exclusion of firms with the largest internal call gaps; and
4. alternate-calendar-time effects where the estimator permits them.

Do not inverse-probability weight missing calls or impute narrative features in v1 unless a separate
missingness analysis and ADR justify the model.

## Consequences

The primary cohort preserves more firms and within-company variation, but the analysis must not
claim a balanced 2017–2024 panel. Missingness may be related to source coverage, company identity,
or time, so robustness-cohort agreement becomes part of the result rather than an optional appendix.

## Validation and reversal

Freeze cohort membership and exclusion reasons before outcome-association analysis. The M1/M2 gate
must report fiscal mapping success for both primary and recent-coverage cohorts. Revisit if fewer
than 15 companies retain 12 mapped calls, recent-cohort coverage becomes too small for useful
inference, or a supplemental authorized transcript source materially changes coverage.
