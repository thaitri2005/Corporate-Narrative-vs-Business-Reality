# RAID register

RAID covers risks, assumptions, issues, and decisions. Review it at least weekly and at every gate.

## Risks

| ID | Risk | Likelihood | Impact | Owner role | Response | Status |
|---|---|---:|---:|---|---|---|
| R-01 | STRUX has no explicit license for intended processing or release | Medium | Critical if scope expands | Project owner | Owner accepted private portfolio risk; prohibit raw/reconstructable release; ADR-010 permits one audited 12-excerpt hosted calibration only; adapter fallback before expanded use | Accepted/monitored |
| R-02 | Continuous Consumer Staples coverage is inadequate | Medium | High | Research lead | Coverage-only cohort analysis before hypothesis selection | Open |
| R-03 | Fiscal/call alignment leaks future information | Medium | Critical | Data engineer | Canonical time spine, golden records, future-invariance tests | Open |
| R-04 | Cross-company XBRL mappings are inconsistent | High | High | Financial reviewer | Versioned mappings, reconciliation, narrow metrics; direct GrossProfit already fails 5-company coverage | Open/evidence confirmed |
| R-05 | Taxonomy is ambiguous or imbalanced | High | High | NLP lead | Pilot found generic `innovation` ambiguity and nonmatch misses; expand pilot before freezing | Open/evidence gathered |
| R-06 | Small company count weakens inference | High | High | Quantitative lead | Conservative inference, effect sizes, influence analysis | Open |
| R-07 | Infrastructure consumes research capacity | Medium | Medium | Tech lead | Adoption gates and modular monolith | Mitigated by design |
| R-08 | Future MkDocs 2 ecosystem changes disrupt docs | Low | Medium | Tech lead | Keep MkDocs 1/Material 9 locked; reassess only during upgrade | Monitoring |
| R-09 | Optional DVC stack includes unfixed `diskcache` advisory PYSEC-2026-2447 | Low in trusted local use | High if cache is attacker-writable | Tech lead / project owner | Keep out of base runtime; owner-controlled local cache only; review before remote; upgrade when patched | Accepted/monitoring |
| R-10 | Small local LLM produces biased weak labels | High | Medium | NLP lead | Calibration required before scale-out; SmolLM2-360M rejected at 41.7% and Qwen2.5-1.5B-Q4 rejected at 63.6% binary agreement | Mitigated/rejected baselines |
| R-11 | Hosted calibration sends restricted excerpts to a provider | Medium | High | Project owner / NLP lead | ADR-010 limits 12 inputs, fixed provider, fine-grained token, no scale-up, and audit metadata; stop on provider/model failure or <0.80 agreement | Accepted/bounded |
| R-12 | Hugging Face included credits are insufficient for the calibration | High | Medium | Project owner | Stop on HTTP 402; do not purchase credits without owner approval; checkpoint successful calls to prevent retransmission after interruption | Closed: hosted path rejected on included tier |
| R-13 | Hosted model output can violate the strict verdict contract | High | Medium | NLP lead | Require structured-output capability and test it on non-restricted synthetic text before any future paid retry; do not reinterpret unparseable completions | Open/future-only |
| R-14 | Repeated interactive local-model launches destabilize the development session | Medium | Medium | Tech lead | Use one hidden loopback-only llama.cpp server per bounded run; synthetic gate before restricted inputs; terminate process deterministically | Mitigated by local-GGUF adapter |

## Assumptions

| ID | Assumption | Validation | Status |
|---|---|---|---|
| A-01 | At least 15 companies have roughly 12 usable calls | Stage 1 coverage report | Unverified |
| A-02 | SEC sources cover core GAAP outcomes | Stage 1 multi-company spike | Unverified |
| A-03 | One mechanism has adequate narrative and outcome coverage | Coverage scorecard | Unverified |
| A-04 | Single-node compute is adequate | Stage 1/2 benchmark | Provisionally supported |
| A-05 | Human annotation/review capacity will be available | Resource assignment | Unverified |

## Current issues

| ID | Issue | Effect | Owner | Resolution |
|---|---|---|---|---|
| I-01 | Sandbox Git ownership differs from repository owner | DVC/Git require local verification overrides | Tech lead | Use per-process safe-directory and ignored DVC `no_scm`; normal user/CI unaffected |
| I-02 | No shared DVC remote selected | No cross-machine cache yet | Project owner | Resolved for Stage 0: local-only; revisit when collaboration requires remote |
| I-03 | Named human owners/reviewer not assigned | Formal gate approvals cannot be signed | Project owner | Confirm names before Stage 1 exit |
| I-04 | DVC security posture required owner acceptance | None after mitigation | Project owner / tech lead | Resolved by ADR-004 |
| I-05 | Truthful SEC request identity has not been supplied | Live SEC feasibility spike cannot run | Project owner | Supply name/organization and monitored contact email; mocked adapter work continues |

## Decisions

Durable design decisions live in `docs/adr/`. Current state:

- ADR-001 modular batch architecture: Accepted.
- ADR-002 Python analytical toolchain: Accepted for Stage 0.
- ADR-003 data-source hierarchy: Proposed pending Stage 1.
- ADR-004 DVC cache isolation: Accepted.
- ADR-005 point-in-time Consumer Staples universe: Accepted.
