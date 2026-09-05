# Corporate Narrative vs. Business Reality

A reproducible NLP and panel-data research system for testing whether changes in Consumer Staples earnings-call narratives precede corresponding changes in business fundamentals.

## Start here

- [Project design](PROJECT_DESIGN.md) — research design, architecture, contracts, and technology rationale.
- [Project plan](PROJECT_PLAN.md) — requirements, work packages, milestones, and delivery gates.
- [Development runbook](docs/runbooks/development.md) — environment setup and verification.

## Stage 0 quick start

Requirements: Python 3.12+ and `uv`.

```bash
uv sync --all-groups
uv run pre-commit install
uv run pytest
uv run cnbr synthetic-run --config configs/data/synthetic.yaml
```

To reproduce the synthetic DVC stage:

```bash
uv sync --extra pipeline
uv run --extra pipeline dvc repro synthetic
```

The synthetic fixture contains no real company or transcript data. Real data belongs under
ignored/DVC-managed paths. STRUX is restricted to private local portfolio analysis because its
published repository has no explicit license; raw or reconstructable transcript content is not a
release artifact and must not be sent to external services.

## Current status

Stage 0 is locally complete. Stage 1 has frozen a 34-company, commit-pinned Consumer Staples
sampling frame, completed a five-company SEC acquisition/coverage spike, and approved a bounded,
checksum-verified STRUX ingestion under the private/local-use constraint.

A five-company M2 vertical slice now runs from canonical transcripts and SEC fiscal alignment
through financial/narrative features to a 102-row point-in-time analytical panel. Manual mapping and
filing reconciliation remain gates before scaling or statistical analysis.
