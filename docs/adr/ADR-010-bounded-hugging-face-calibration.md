# ADR-010: Bounded Hugging Face hosted weak-label calibration

> Status: Accepted with constraints  
> Date: 2026-09-06

## Context

The local `SmolLM2-360M-Instruct` calibration produced `Yes` for all 12 balanced, human-reviewed
tasks and only 0.417 exact agreement. It is rejected as a weak-label source. The owner explicitly
authorized a Hugging Face hosted alternative on 2026-09-06 for this personal portfolio project.

This is an exception to the local-only default in ADR-007. STRUX carries an ambiguous upstream
license, so this exception is intentionally narrow and does not establish a general right to send
the corpus to a third party.

## Decision

Run at most 12 deterministic calibration tasks: one pre-existing human-reviewed task for each
`candidate_topic × selection_mode` cell. The code sends only the candidate-topic name and a
maximum 1,600-character excerpt for each selected task. No raw corpus file, SEC record, participant
table, task packet, or unselected call is sent.

Use the Hugging Face Inference Providers API with a fine-grained `HF_TOKEN` carrying only **Make
calls to Inference Providers**. Configure a fixed provider (`groq`), model
(`openai/gpt-oss-20b`), deterministic decoding, 60-second request timeout, and four-token maximum
response. The token is supplied only through the local environment and is never written to
configuration, outputs, Git, logs, or reports. The owner explicitly authorized the fixed
third-party routed provider on 2026-09-06 after the originally selected `hf-inference` provider
rejected the Qwen model before inference.

Capture the requested model revision and the Hub-resolved SHA, provider, configuration hash,
per-input SHA-256, aggregate agreement, and verdict counts. Checkpoint each successful request in
ignored local storage so a provider/credit failure cannot cause duplicate excerpt transmission.
Commit only non-reconstructable aggregate reports after review. Human labels remain the evaluation
reference. The run cannot label additional records; any scale-up needs a new owner decision and ADR.

## Preconditions and stop conditions

Before a request, the CLI requires `HF_TOKEN`, validates the bounded configuration, and resolves the
model revision. Stop without fallback routing if the fixed provider or model is unavailable. Stop
after the 12-task calibration if output is unparseable, if results reveal systematic collapse, or if
agreement is below the pre-declared 0.80 threshold. A passing calibration is evidence for a further
decision, not permission to scale.

Hugging Face documents that its router does not store request bodies or responses for training and
may retain logs for up to 30 days; downstream provider policies still apply. This project therefore
treats the excerpts as externally processed restricted data, not as public data. See the [Hugging
Face Inference Providers documentation](https://huggingface.co/docs/inference-providers/index) and
[security documentation](https://huggingface.co/docs/inference-providers/en/security).

## Consequences and reversal

This introduces a small API dependency and a narrowly scoped external-data risk, but avoids local
hardware escalation and evaluates a production-relevant API integration. Revoke/delete the token
and remove the hosted configuration if the owner withdraws approval. Revert to human labeling or a
rights-cleared corpus if the exception becomes unsuitable.
