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

## M3 pilot and bounded hosted-calibration decision

`configs/data/lexical_baseline.yaml` and `cnbr lexical-baseline` implement a local-only dictionary
discovery baseline for six draft Consumer Staples constructs. Its aggregate output is explicitly
non-confirmatory and is not joined to the analytical panel. See `TAXONOMY_DRAFT.md` for collision
risks, null semantics, and the annotation/benchmark gate required for promotion.

The two local pilot packets yielded 42 single-reviewer judgments. They are sufficient to narrow the
draft taxonomy and choose the next annotation design, but not to train/evaluate a semantic model or
freeze labels. Details and the promotion decision are recorded in `TAXONOMY_DRAFT.md`.

The local 360M checkpoint was rejected after a 12-task calibration (41.7% agreement and an
all-`Yes` collapse). ADR-010 records the owner's approval for a separate 12-excerpt Hugging Face
hosted calibration. It has fixed provider/model settings, an environment-only fine-grained token,
an audit manifest, and no scale-up authority. The command is `cnbr hosted-weak-label --config
configs/data/hosted_weak_label.yaml`. On 2026-09-06, the original `hf-inference` model choice was
rejected before inference; the owner approved fixed Groq routing through Hugging Face. Two attempts
both stopped at request 10 with HTTP 402 for exhausted included credits. The second attempt preserved
nine text-free checkpoint rows; all nine responses were unparseable under the four-token verdict
contract. This hosted calibration is rejected as inconclusive: no aggregate result, taxonomy change,
or scale-up occurred. The code now checkpoints each completed request locally before another attempt.

## Financial reconciliation control

`cnbr financial-reconcile` independently recomputes every resolved canonical value from its stored
fact operands, fails on missing operands/formula mismatches, and emits a stratified, text-free CSV
sample. This closes the local arithmetic/provenance portion of the reconciliation gate; independent
filing-presentation review remains required before M2 acceptance because the local snapshot contains
Company Facts, not filing-rendered statements.

Gross margin is intentionally absent because the earlier concept audit rejected universal direct
comparability. No GPU, database, or distributed system is required. The ADR-010 calibration is the
only approved hosted API operation.

Run `cnbr fiscal-review-build --config configs/data/review.yaml` to create a restricted local HTML
packet and metadata-only CSV checklist for 15 early/middle/late calls (three per company). The
command never overwrites an existing checklist. The HTML contains transcript excerpts and must not
be published; reviewer notes must not copy transcript text.

## Local GGUF replacement path

`configs/data/local_gguf_weak_label.yaml` defines a CPU-only alternative using the official pinned
Qwen2.5 1.5B Q4_K_M GGUF artifact. The 1.12 GB model is cached outside Git. It runs through one
hidden loopback-only `llama-server` process per calibration, rather than launching an interactive
CLI once per task; this prevents repeated model loads and keeps model work separate from the coding
agent session. A three-case synthetic JSON-contract gate must pass before any restricted task is
read. The adapter always terminates the local server at the end of a run and does not use an API,
cloud service, or GPU.
