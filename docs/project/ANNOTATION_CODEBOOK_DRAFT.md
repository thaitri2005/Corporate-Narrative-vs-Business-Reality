# Annotation codebook draft — refinement packet

> Status: Draft for local human review only  
> Scope: `cost_pressure`, `demand_volume`, `supply_chain`

For each excerpt, label whether it genuinely discusses the displayed candidate topic. Candidate
topics are hypotheses, not answers. Use `Yes` only for explicit or clearly synonymous discussion,
`No` for clearly unrelated text, and `Unsure` only when the excerpt cannot resolve a plausible
reading. Do not infer from company knowledge or adjacent missing context.

| Topic | Yes | No / boundary |
|---|---|---|
| `cost_pressure` | Input inflation, commodity, freight, labor, or other costs affecting economics | Generic savings, a cost figure with no pressure/driver, or pricing-only discussion |
| `demand_volume` | Consumer demand, units, traffic, volume, consumption, or elastic response | Production/warehouse volume, capacity, or sales dollars without demand/volume meaning |
| `supply_chain` | Availability, shortages, suppliers, logistics disruption, inventory flow, or sourcing constraint | Generic vendor mention without supply availability/logistics meaning |

Review the 12 candidate matches and 12 lexical-nonmatch controls separately. The packet excludes the
deterministic examples already used in the first pilot. Export labels locally; never publish the HTML
or copy excerpts into notes.
