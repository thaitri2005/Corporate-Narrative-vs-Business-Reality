# SEC Company Facts concept-coverage screen

> Status: Stage 1 availability evidence; not a normalized financial dataset  
> Sample: KO, PG, COST, WMT, MO  
> Fiscal labels: 2017–2024, expected 32 per company

## Purpose and method

This screen asks whether candidate US-GAAP concept families appear often enough to justify deeper
fiscal and semantic reconciliation. It reads only the locally cached, SHA-256-bound Company Facts
responses. For each company and metric it unions distinct `(fy, fp)` labels from 10-K, 10-K/A,
10-Q, and 10-Q/A facts denominated in USD.

The expected 32 labels represent `Q1`, `Q2`, `Q3`, and `FY` across eight fiscal years. `FY` is not
treated as an already derived fourth quarter. Duplicate comparative facts and amendments count once.

## Results

| Metric family | Candidate raw concepts | Companies | Minimum | Median | Maximum |
|---|---|---:|---:|---:|---:|
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet`, `SalesRevenueGoodsNet` | 5/5 | 100% | 100% | 100% |
| Operating income | `OperatingIncomeLoss` | 5/5 | 100% | 100% | 100% |
| Inventory | `InventoryNet` | 5/5 | 100% | 100% | 100% |
| CapEx | `PaymentsToAcquirePropertyPlantAndEquipment` | 5/5 | 100% | 100% | 100% |
| Direct gross profit | `GrossProfit` | 3/5 | 0% | 12.5% | 100% |

Gross-profit detail is heterogeneous: KO and MO have 32/32 labels, COST 4/32, and PG/WMT 0/32.
Accordingly, direct gross profit is not a cohort-wide standardized outcome.

## Interpretation

- Revenue, operating income, inventory, and CapEx pass the availability screen and move to value,
  duration, dimension, amendment, and filing-timestamp reconciliation.
- Gross margin stays conditional. It may be derived from validated revenue and cost concepts for
  specific companies, but it cannot be assumed or silently mixed with direct `GrossProfit`.
- A 100% label count does not imply 100% usable quarterly observations. Company Facts includes annual,
  year-to-date, amended, and comparative facts that require deterministic selection.
- Non-calendar fiscal companies COST, PG, and WMT remain in the sample specifically to test period
  mapping rather than forcing calendar-quarter assumptions.

## Reproducibility

Run locally after the SEC spike:

```powershell
uv run cnbr sec-coverage --config configs/data/sec_concept_coverage.yaml
```

Machine outputs are `reports/tables/sec_concept_coverage.csv` and `.json`, tracked through DVC. The
JSON contains the resolved configuration hash and SHA-256 of every Company Facts input.

## Next checks

1. Select one fact per filing/period with explicit amendment and filed-at rules.
2. Separate instant from duration facts and distinguish quarterly, YTD, and annual durations.
3. Derive Q4 and YTD-to-quarter flows only when duration and prior-period lineage are valid.
4. Reconcile a manual golden sample to filed statements for all five companies.
5. Decide whether operating margin becomes the common margin outcome and where company-specific
   gross-margin mappings remain defensible.
