# Taxonomy draft 0.1 — local lexical discovery baseline

> Status: implemented discovery baseline; not an annotation codebook or research label set  
> Updated: 2026-09-05

## Decision

We begin M3 with a transparent, local-only dictionary baseline. It runs against the canonical
utterance table on the workstation and releases only aggregate feature rows. It does not download a
model, use a GPU, transmit STRUX text, or claim that a phrase match is a semantic label.

The baseline is a deliberate first rung in the approved model ladder: it supports corpus exploration,
pilot sampling strata, and future hard-negative design. It is excluded from confirmatory analysis and
must not select outcomes, hypotheses, or model thresholds.

## Draft discovery topics

| Stable ID | Construct | Intended mechanism | Known collision risk |
|---|---|---|---|
| `pricing` | Pricing / price-mix discussion | Revenue and margin | Historical prices, competitor pricing |
| `cost_pressure` | Input-cost or inflation pressure | Margin and CapEx | Cost savings / generic cost mentions |
| `demand_volume` | Consumer demand or sales volume | Revenue growth | Operational production volume |
| `supply_chain` | Availability / supply-chain constraint | Inventory and revenue | Generic supplier references |
| `portfolio_expansion` | Innovation, launches, expansion | Future revenue / CapEx | Geographic or capacity expansion |
| `guidance_outlook` | Guidance and outlook | Expectations, not performance | Boilerplate forward-looking statements |

Regex patterns live in `configs/data/lexical_baseline.yaml`, not application code. A turn can match
multiple draft topics. Features use the precomputed word count of every eligible turn containing at
least one pattern, divided by all eligible words in the same call/view. This is a mention-weighted
discovery statistic, not a calibrated probability or causal exposure.

## Views and guardrails

- Included views: management prepared remarks, management Q&A, analyst Q&A.
- Blank/source-footer turns are excluded under the same quality rules as structural features.
- Empty eligible views are retained with a null share; absence never becomes a zero signal.
- Output contains identifiers, counts, shares, topic/config versions, and hashes—never text or match
  excerpts.
- The consumer-staples draft is additive and remains version `0.1-draft` until a pilot annotation
  codebook, double annotation, and adjudication change it to a frozen taxonomy version.

## Promotion gate

Before any dictionary feature can enter a study dataset, we need a stratified pilot sample, written
inclusion/exclusion rules, hard negatives, inter-annotator agreement targets, and a locked test set.
Embedding or transformer evaluation requires a separate measured tokenizer/model benchmark and any
needed model download approval.
