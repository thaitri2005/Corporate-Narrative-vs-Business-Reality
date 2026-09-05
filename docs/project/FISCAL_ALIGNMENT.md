# Five-company fiscal-alignment thin slice

> Status: Automated contract checks passed; manual sample review pending  
> Updated: 2026-09-05

## Scope and result

The thin slice uses the already cached SEC submissions and Company Facts for KO, PG, COST, WMT, and
MO. It covers 160 non-amended 10-Q/10-K filings: exactly 32 fiscal periods per company. Amendments
remain source versions and do not create additional quarters.

All 102 available STRUX calls for these companies map uniquely to the latest preceding fiscal period
end within the predeclared 75-day window. Observed lags range from 15 to 45 days; no call is unmapped
and no period receives multiple calls.

## Mapping rule

1. Restrict the filing spine to base 10-Q/10-K records and bind facts by exact accession and report
   date.
2. Obtain SEC fiscal year/period labels and the shortest current-period revenue-family boundary.
3. Use adjacent period ends to resolve a quarter start when an annual/YTD fact starts earlier; fail
   on non-sequential fiscal labels or a boundary that starts after the inferred quarter.
4. Map each call to the latest preceding period end only when lag is at most 75 days.
5. Preserve STRUX call dates at date precision under registry schema 2.0. Never fabricate a time or
   infer fiscal labels from the call's calendar year.

The resulting fiscal-period and call-mapping Parquet files retain deterministic company/call keys,
filing acceptance timestamps, accession-bound period evidence, rule version, and input/output hashes.

## What this proves—and does not prove

The automated result demonstrates technically consistent alignment across calendar, non-calendar,
and 52/53-week reporters on the five-company sample. It does not replace manual verification against
reported-quarter language for a stratified sample. That review remains a gate before scaling the
mapping or treating the result as trusted canonical data.

The next financial step extracts provenance-rich facts for revenue, operating income, inventory, and
CapEx, then classifies direct-quarter/YTD/annual/instant observations. Gross profit remains deferred
because direct concept coverage is not comparable across the sample.

## Fact-occurrence extraction

The accession-bound extractor now retains 2,279 relevant Company Facts occurrences across the five
companies in a 118,560-byte Parquet. Each row preserves source concept, unit, exact JSON value,
start/end, duration class, SEC fiscal labels/frame, accession, form, filing and acceptance time,
amendment/current-period flags, source item locator, and file hash. All 160 base filings have at
least one current USD occurrence for each of revenue, operating income, inventory, and CapEx.

This is deliberately an occurrence layer, not a canonical-value table. Overlapping revenue concepts
and quarter/YTD observations remain separate for the next reconciliation and selection stage.

## Canonical quarterly values

A versioned company-specific revenue priority and common metric rules now resolve 637 of 640 expected
company-quarter-metric values. The table contains 307 direct-quarter values, 160 direct inventory
instants, and 170 values derived as cumulative minus prior cumulative with both operand fact IDs.

Three early-window flow values remain null because their required prior cumulative filing precedes
the acquired boundary. They are labeled `unresolved_missing_prior_cumulative`, not imputed. This is
an expected left-boundary limitation and demonstrates that the resolver fails visibly rather than
manufacturing a quarter. Filing-sample reconciliation remains open before M2 acceptance.

The mechanical feature stage then produced 1,234 long-form rows: 159 operating margins, 158
CapEx/revenue ratios, 140 revenue YoY values, 140 inventory YoY values, and their resolved canonical
inputs. Same-quarter year-over-year comparisons require an actual prior fiscal-year key; missing
predecessors remain absent. No narrative/outcome association has been run.

A matching role/section structural baseline covers all 102 mapped calls and 983,194 eligible words.
It supplies leakage-safe corpus diagnostics for the thin slice, but deliberately does not stand in
for the later theory-grounded narrative taxonomy or semantic model.

The point-in-time join now materializes 102 unique analytical rows. Next-quarter operating margin
and CapEx/revenue are present for all 102; revenue YoY and inventory YoY are present for 101. The
33,721-byte artifact is a join/lag deliverable only—no coefficient, correlation, or outcome-guided
selection has been computed.
