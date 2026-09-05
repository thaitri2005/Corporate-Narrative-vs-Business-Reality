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
