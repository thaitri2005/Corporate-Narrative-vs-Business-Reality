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

## Pilot task packet

`cnbr annotation-pilot --config configs/data/annotation_pilot.yaml` creates a deterministic,
Label Studio-compatible JSON task packet and a click-through local HTML review page. It includes
draft-topic metadata and text only in ignored `data/review/`; the committed manifest records counts,
hashes, and the taxonomy revision without copying text. Candidate topics are sampling aids, not
pre-applied labels. The local page exports a text-free label JSON; import the task packet into Label
Studio only after defining the annotation interface and codebook decisions.

After the initial candidate-match pilot, run `configs/data/annotation_controls.yaml` to create a
small lexical-nonmatch control packet. It measures whether the draft dictionary misses meaningful
topic language; it is not a model evaluation set.

## Pilot result and decision — 2026-09-06

One reviewer completed 42 local tasks: 24 candidate matches and 18 lexical-nonmatch controls.
Candidate matches received 23 Yes and 1 No. Controls received 13 No, 3 Yes, and 2 Unsure. The
control Yes results occurred once each for cost pressure, demand/volume, and portfolio expansion;
the two Unsure results were cost pressure and supply chain. The candidate-match No was the generic
`innovation` pattern under portfolio expansion.

Decision: retain `pricing` and `guidance_outlook` as high-precision discovery candidates; retain
`cost_pressure`, `demand_volume`, and `supply_chain` for a larger pilot with expanded wording;
keep `portfolio_expansion` explicitly provisional and do not promote generic `innovation` as a
standalone portfolio-expansion signal. No construct is yet a validated research label, and no
classifier or outcome analysis may use this pilot as a test set.

## Local LLM calibration — rejected baseline

The pinned local checkpoint `HuggingFaceTB/SmolLM2-360M-Instruct` at revision
`cbcad7f4d160a10174f725b968ab6faf2a76399e` completed a balanced 12-task CPU calibration: one
phrase-match and one nonmatch control per topic. It returned a parseable Yes for every task and
achieved only 41.7% exact agreement with the human labels. It is rejected for weak-label generation.
No generated label enters the taxonomy, training, or analytical dataset; the human/dictionary path
remains selected.

## Hosted calibration gate

ADR-010 authorizes one distinct, deterministic 12-task calibration through Hugging Face Inference
Providers after the local baseline rejection. It is a model-selection measurement, not a labeling
run: exact agreement must reach 0.80 with parseable responses before the owner is asked to consider
any subsequent pilot. It never changes taxonomy status, creates ground truth, or authorizes broader
external transcript processing.

## Hosted calibration outcome — rejected on included tier

The fixed Groq route was attempted twice through Hugging Face after the local-model rejection. Both
attempts exhausted included credits at request 10. The second attempt safely checkpointed nine
responses, all unparseable under the predeclared one-word verdict contract. This is inconclusive
and rejected as weak-supervision evidence. It does not alter the taxonomy, and no further hosted
attempt will occur without a new paid-budget and structured-output decision.

## Local GGUF replacement gate

The free local replacement is the official Qwen2.5 1.5B Q4_K_M GGUF model, run CPU-only through
llama.cpp. It is a distinct calibration and does not reuse or reinterpret hosted outputs. The model
reliably distinguished explicit positive and unrelated synthetic pricing cases but treated an
ambiguous case as `No`; it is therefore restricted to binary Yes/No discovery. Human `Unsure`
judgments are excluded from its agreement denominator, retained as human evidence, and never
collapsed into model ground truth. Before reading any annotation task, the binary synthetic gate
must pass. Failure keeps the human/dictionary path selected and records no transcript-derived weak
labels.

## Local GGUF calibration outcome — rejected

The synthetic gate passed, then the pinned Qwen2.5 1.5B Q4_K_M model completed the bounded 12-task
local calibration. Against 11 comparable human Yes/No judgments, it achieved 63.6% exact agreement,
below the 0.80 promotion threshold. It is rejected for weak-label generation. No output enters the
taxonomy, training, or analytical dataset; the human/dictionary path remains selected.

## Human refinement packet — ready

The next local packet narrows effort to the three constructs whose initial controls exposed recall
or boundary uncertainty: `cost_pressure`, `demand_volume`, and `supply_chain`. It contains 24 new
deterministically selected tasks: 12 lexical matches and 12 lexical-nonmatch controls, four per
topic in each mode. It skips all previously reviewed deterministic selections. The accompanying
codebook is `ANNOTATION_CODEBOOK_DRAFT.md`; exports remain in ignored `data/review/`.
