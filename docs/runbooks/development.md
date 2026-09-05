# Development runbook

## Prerequisites

- Python 3.12+
- Git
- uv

## Setup

```bash
uv sync --all-groups
uv run pre-commit install
```

Optional DVC dependency:

```bash
uv sync --extra pipeline
```

## Verification

```bash
uv lock --check
uv run ruff format --check src tests
uv run ruff check src tests
uv run pyright
uv run pytest
uv run mkdocs build --strict
```

## Synthetic thin slice

```bash
uv run cnbr synthetic-run --config configs/data/synthetic.yaml
```

It creates ignored Parquet, CSV, and run-manifest outputs under `data/` and `reports/tables/`. The manifest records code state, configuration/input hashes, row counts, and output hashes. Its timestamp changes; deterministic run ID and data hashes do not.

## DVC reproduction

```bash
uv run --extra pipeline dvc repro synthetic
```

Stage 0 intentionally has no shared DVC remote. That choice depends on collaboration, provider rights, cost, and preferred storage platform.

## Failure recovery

The synthetic stage owns only paths declared in `dvc.yaml`; rerunning replaces those generated artifacts. Real raw snapshots will be append-only and must not be deleted during retry.

## Differently owned worktrees

If Git reports dubious ownership, avoid a global configuration change and use a per-command override:

```bash
git -c safe.directory="D:/Corporate-Narrative-vs-Business-Reality" status
```
