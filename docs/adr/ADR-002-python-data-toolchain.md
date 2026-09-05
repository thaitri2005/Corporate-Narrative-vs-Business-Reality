# ADR-002: Use Python, uv, Polars, DuckDB, and Parquet

- Status: Accepted for Stage 0; components remain reviewable after the spike
- Date: 2026-09-05
- Owners: Tech lead
- Related design: `PROJECT_DESIGN.md`, Section 9

## Context

The project must support transcript parsing, NLP, tabular transformations, panel models, and reproducible research artifacts using current, common tools and open interchange formats.

## Decision drivers

- NLP and statistical ecosystem coverage.
- Exact dependency resolution.
- Efficient single-node processing.
- Inspectable SQL and cross-platform use.
- Low custom infrastructure and low lock-in.

## Considered options

- Python with uv, Polars, DuckDB, and Parquet.
- Python with pandas and SQLite only.
- R-centered research stack.
- Warehouse/Spark-centered data stack.

## Decision

Use Python 3.12-compatible code, uv-managed project/lock files, Polars for production transformations, DuckDB for SQL inspection and reconciliation, and Parquet for durable analytical tables.

## Consequences

Polars and DuckDB must have distinct ownership to avoid duplicated logic. Team members need familiarity with Polars expressions. Exact versions live in the lockfile rather than design prose.

## Validation and rollback

CI installs from the lock and runs on Windows and Linux. If a component fails compatibility or usability tests, replace it behind Parquet/CLI boundaries and supersede this ADR.
