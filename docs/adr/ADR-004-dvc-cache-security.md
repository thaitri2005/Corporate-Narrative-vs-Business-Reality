# ADR-004: Retain DVC as an optional tool with trusted cache isolation

- Status: Accepted
- Date: 2026-09-05
- Owners: Project owner / tech lead
- Related design: `PROJECT_DESIGN.md`, Section 12

## Context

DVC 3.67.1 provides the planned file-based DAG and data-artifact lineage but currently depends on `diskcache` 5.6.3. PYSEC-2026-2447 / CVE-2025-69872 reports unsafe pickle deserialization if an attacker can write to the cache directory and a user later reads it. No patched `diskcache` release is listed as of this decision.

## Decision drivers

- Preserve standard artifact lineage and reproducible batch stages.
- Keep the base runtime and CI dependency set free of known vulnerabilities.
- Avoid processing cache data controlled by untrusted users.
- Retain a low-cost path to replace DVC.

## Considered options

1. Retain DVC as an optional dependency with owner-controlled local caches.
2. Remove DVC and use only CLI commands plus custom manifests.
3. Replace DVC immediately with a heavier orchestration/versioning platform.
4. Stop all pipeline-lineage work until an upstream patch exists.

## Decision

Retain DVC in the optional `pipeline` extra. Use local-only, project-owner-controlled cache storage initially. Do not ingest caches or DVC artifacts from untrusted/shared writable locations. Keep DVC out of the base runtime and base dependency audit. Record the advisory explicitly rather than suppressing it without context.

## Consequences

The standard base environment audits cleanly. Installing the pipeline extra produces a known medium-severity advisory until upstream mitigation is released. Any future shared remote must prevent untrusted write access and receive a security/access review first.

## Validation and rollback

Review the advisory during dependency upgrades and before configuring a remote. Upgrade when a compatible patch exists. If exposure changes or policy disallows the exception, remove DVC and retain the Python CLI, artifact manifests, Parquet contracts, and `dvc.yaml` stage structure as migration inputs.
