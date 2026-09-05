# M2 trusted-canonical-data progress

> Status: Thin slice implemented; manual audits and scale-out remain  
> Updated: 2026-09-05

## Implemented vertical slice

The local DVC graph now produces a complete five-company path:

```text
pinned STRUX + SEC snapshots
  -> canonical calls/participants/utterances
  -> accession-bound fiscal periods and call mappings
  -> provenance-rich SEC fact occurrences
  -> canonical quarterly financial values
  -> financial and narrative structural features
  -> point-in-time analytical thin-slice panel
```

The analytical artifact contains 101 unique company/fiscal-quarter observations across KO, PG,
COST, WMT, and MO. Each row carries role/section narrative structure, current financial controls,
and fiscal-keyed next-quarter outcomes. Lead coverage is 101/101 for operating margin,
CapEx/revenue, revenue YoY, and inventory YoY. The panel is 33,573 bytes.

No outcome association has been estimated or inspected. This protects the pre-analysis workflow
while taxonomy, manual reconciliation, and cohort rules are still being validated.

## Remaining M2 gates

- Complete the remaining local fiscal-mapping sample review; one confirmed STRUX date/content
  conflict (COST, source date 2017-05-31) is quarantined in `configs/data/align.yaml` rather
  than silently repaired.
- Reconcile a stratified direct and cumulative-derived financial sample to filing presentation.
- Define review thresholds and store adjudication without transcript text in Git.
- Scale SEC acquisition/fiscal normalization from five companies only after the sample passes.
- Finalize the eligible 28-company candidate and 12-company recent-coverage robustness cohorts.
- Add semantic chunks only after a tokenizer/model benchmark; canonical utterances remain unchanged.

## M3 pilot started without external model processing

`configs/data/lexical_baseline.yaml` and `cnbr lexical-baseline` implement a local-only dictionary
discovery baseline for six draft Consumer Staples constructs. Its aggregate output is explicitly
non-confirmatory and is not joined to the analytical panel. See `TAXONOMY_DRAFT.md` for collision
risks, null semantics, and the annotation/benchmark gate required for promotion.

## Financial reconciliation control

`cnbr financial-reconcile` independently recomputes every resolved canonical value from its stored
fact operands, fails on missing operands/formula mismatches, and emits a stratified, text-free CSV
sample. This closes the local arithmetic/provenance portion of the reconciliation gate; independent
filing-presentation review remains required before M2 acceptance because the local snapshot contains
Company Facts, not filing-rendered statements.

Gross margin is intentionally absent because the earlier concept audit rejected universal direct
comparability. No external API, cloud execution, GPU, database, or distributed system is required.

Run `cnbr fiscal-review-build --config configs/data/review.yaml` to create a restricted local HTML
packet and metadata-only CSV checklist for 15 early/middle/late calls (three per company). The
command never overwrites an existing checklist. The HTML contains transcript excerpts and must not
be published; reviewer notes must not copy transcript text.
