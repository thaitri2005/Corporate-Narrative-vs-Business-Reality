# ADR-006: Use bounded file-manifest SEC acquisition

- Status: Accepted
- Date: 2026-09-05
- Owners: Project lead and tech lead

## Context

The approved universe has 34 companies. Stage 1 needs SEC submissions and Company Facts JSON, not a
broad archive of all filings. A separate SEC-ingestion project plan supplied by the owner describes
three-worker collection, thread-safe rate limiting, bounded retries, atomic writes, checksums,
resumability, and SQLite checkpoints for 10,000-filing batches.

That plan is reference evidence, not an instruction for this repository. Its reliability controls
apply; its all-company discovery, raw filing HTML/TXT, 10,000-record batching, server deployment, and
SQLite metadata database do not match this bounded workload.

## Decision

Use the existing `httpx` adapter and DVC/file-manifest architecture. Run no more than three worker
threads and start no more than eight SEC requests per second process-wide. Require a truthful runtime
User-Agent. Retry 429 and transient 5xx responses with bounded exponential/`Retry-After` backoff.
Validate every response as a JSON object, write through same-directory temporary files and atomic
replacement, calculate SHA-256, preserve partial failures in a manifest, and reuse valid cached
files on rerun.

Do not add SQLite for the feasibility or 34-company acquisition. Each CIK/endpoint has a deterministic
path, so file existence plus validation and the DVC/JSON manifests provide adequate checkpointing.

## Consequences

- Ten endpoint artifacts for five companies were acquired successfully using approximately 19.9 MiB.
- Worker count and request rate are schema-validated hard limits, not operator suggestions.
- User-Agent identity remains in runtime configuration; only its SHA-256 enters the ignored raw
  manifest.
- Multiple concurrent processes are unsupported. If coordination or tens of thousands of artifacts
  become necessary, revisit a SQLite job ledger through a new ADR.

## Validation and rollback

Mocked tests cover identification, CIK normalization, retry, rate configuration, atomic writes,
hashing, and cache reuse. The live feasibility manifest records counts, sizes, URLs, and hashes.
The adapter can be replaced without changing normalized financial contracts.
