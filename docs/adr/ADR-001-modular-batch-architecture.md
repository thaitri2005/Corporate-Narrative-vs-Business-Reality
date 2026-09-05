# ADR-001: Use a local-first modular batch architecture

- Status: Accepted
- Date: 2026-09-05
- Owners: Project lead / tech lead
- Related design: `PROJECT_DESIGN.md`, Sections 5 and 10

## Context

The project processes a modest research corpus into company-quarter features and statistical outputs. It needs repeatability, auditability, and replaceable components, but not online serving or concurrent application writes.

## Decision drivers

- Research reproducibility and source-to-result lineage.
- Low operational burden for a small team.
- Clear module ownership and replaceable providers/models.
- Windows development and Linux CI.
- A path to shared storage or orchestration without redesign.

## Considered options

1. Modular Python monolith executed as a batch DAG.
2. Notebook-centered analysis.
3. Service-oriented architecture with APIs and a database.
4. Warehouse-first SQL transformation project.

## Decision

Use an installable Python package with narrow modules, CLI entry points, typed/versioned Parquet boundaries, DVC pipeline lineage, and local-first execution.

## Consequences

The system stays easy to run and inspect and avoids premature services. Module discipline must be enforced through contracts and reviews. DVC and local artifact workflows require a Windows usability check.

## Validation and rollback

Validate with a synthetic raw-to-report stage on Windows and Linux CI. Adopt orchestration, a database, or object storage only after measured scheduling, concurrency, or collaboration needs; the CLI and contracts remain migration boundaries.
