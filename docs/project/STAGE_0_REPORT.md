# Stage 0 verification report

> Status: Locally complete; hosted CI pending repository push  
> Updated: 2026-09-05

## Established

- Python 3.12 project using uv and a committed lockfile.
- Installable `cnbr` package and CLI.
- Ruff, Pyright, pytest/coverage, Hypothesis, pre-commit, secret scan, dependency audit, and MkDocs configuration.
- Windows/Linux GitHub Actions quality matrix.
- DVC pipeline definition and local repository configuration.
- Synthetic legal fixture and deterministic raw → Parquet → quarterly feature → CSV/manifest path.
- Structured JSON logging and run/config/input/output lineage.
- ADRs for architecture, toolchain, and provisional data sources.
- Governance, RAID, hypothesis, issue, and pull-request templates.

## Local verification evidence

- Ruff formatting: pass.
- Ruff lint: pass.
- Pyright strict checks: pass after one documented Polars partial-unknown override.
- pytest: 5 tests pass; 81% branch-aware coverage.
- MkDocs strict build: pass on MkDocs 1.x/Material 9.x; future MkDocs 2 warning recorded as R-08.
- Synthetic CLI: 8 input utterances → 4 company-quarter feature rows.
- DVC reproduction: pass; `dvc.lock` generated.

## Remaining exit evidence

- Secret scan produced no findings with sandbox-safe Git configuration.
- Base runtime/CI dependency audit: pass, no known vulnerabilities.
- Optional DVC environment audit: one unfixed medium-severity `diskcache` advisory; retained with owner-approved mitigation in ADR-004.
- Second DVC run: pass, stage unchanged and up to date.
- GitHub-hosted Windows/Linux CI pass after an authorized push/PR.
- Independent reviewer assignment before the Stage 1 exit.

## Security decision pending

DVC 3.67.1 currently depends on `diskcache` 5.6.3. PYSEC-2026-2447 / CVE-2025-69872 concerns unsafe pickle deserialization when an attacker can write to the cache directory and a user later reads it. No patched release is listed. The approved design retains DVC as optional, keeps the base environment clean, uses owner-controlled local caches, prohibits untrusted/shared writable caches, and requires review before any remote. See ADR-004.
