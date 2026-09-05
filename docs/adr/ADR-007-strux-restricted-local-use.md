# ADR-007: Use STRUX only for restricted local portfolio analysis

> Status: Accepted with constraints  
> Date: 2026-09-05

## Context

STRUX provides structured earnings-call sections and speaker roles at a useful portfolio-project
scale. Its public Hugging Face repository is downloadable but declares no explicit dataset license
and attributes underlying transcript text to Motley Fool. Public access is not equivalent to a
redistribution license.

This is a private personal/CV project intended to demonstrate data engineering, NLP, and empirical
research ability. The project owner explicitly chose to proceed after the ambiguity was explained.

## Decision

Acquire only the two `full` Parquet shards pinned to revision
`8c3d39f2d70a8fa2d619f8c7bef9176efcb89520`. Verify each published SHA-256, store raw and filtered
data outside Git, and filter locally to the approved Consumer Staples universe.

Do not send transcript content to external APIs/cloud services. Do not publish raw text, excerpts,
row-level data, or derived artifacts from which transcript content can be reconstructed. A public
portfolio may include code, tests, source attribution, lineage metadata, methods, schemas, and
non-reconstructable aggregates.

This decision records owner risk acceptance; it does not assert that STRUX or its underlying text
is licensed for redistribution.

## Alternatives considered

- Request written permission before acquisition: safest rights path, but unnecessary for the
  owner's chosen private portfolio boundary and potentially open-ended.
- Replace STRUX immediately: reduces ambiguity but adds sourcing cost and may weaken the structured
  role demonstration.
- Scrape transcripts independently: rejected because it increases engineering and terms risk.

## Consequences and reversal

The pipeline remains source-adapter based, so STRUX can be replaced without changing downstream
contracts. Any team, commercial, hosted, external-model, or data-release use must stop at a gate and
receive a new source decision. Delete local STRUX artifacts and switch the adapter if the owner
withdraws acceptance or upstream objects fail verification.
