from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

from cnbr.config import FinancialNormalizeConfig

FLOW_METRICS = {"revenue", "operating_income", "capital_expenditure"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _choose_reconciled(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"No candidates for {label}")
    values = {str(row["value_raw"]) for row in rows}
    if len(values) != 1:
        raise ValueError(f"Conflicting candidates for {label}: {sorted(values)}")
    return min(rows, key=lambda row: str(row["fact_id"]))


def _concept_candidates(
    facts: pl.DataFrame,
    accession: str,
    metric: str,
    priorities: list[str],
) -> tuple[str, list[dict[str, Any]]]:
    current = facts.filter(
        (pl.col("accession_number") == accession)
        & (pl.col("metric") == metric)
        & pl.col("is_current_period")
        & ~pl.col("is_amendment")
        & (pl.col("unit") == "USD")
    )
    for concept in priorities:
        selected = current.filter(pl.col("concept_raw") == concept)
        if not selected.is_empty():
            return concept, selected.to_dicts()
    raise ValueError(f"No configured concept for {metric} in {accession}")


def normalize_financial_values(
    config: FinancialNormalizeConfig, repo_root: Path
) -> dict[str, object]:
    """Resolve canonical quarter values with explicit direct/derived provenance."""
    facts = pl.read_parquet(repo_root / config.occurrence_path)
    periods = pl.read_parquet(repo_root / config.fiscal_periods_path).sort(
        "company_id", "fiscal_year", "fiscal_quarter"
    )
    filings = pl.read_parquet(repo_root / config.filing_index_path).filter(~pl.col("is_amendment"))
    universe = pl.read_parquet(repo_root / config.universe_path).select("company_id", "ticker")
    ticker_by_company = dict(universe.iter_rows())
    accession_by_period_end = {
        (str(row["ticker"]), str(row["report_date"])): str(row["accession_number"])
        for row in filings.iter_rows(named=True)
    }
    results: list[dict[str, object]] = []
    previous_cumulative: dict[tuple[str, str], dict[str, Any]] = {}
    for period in periods.iter_rows(named=True):
        company_id = str(period["company_id"])
        ticker = str(ticker_by_company[company_id])
        fiscal_year = int(period["fiscal_year"])
        fiscal_quarter = int(period["fiscal_quarter"])
        period_start = str(period["period_start"])
        period_end = str(period["period_end"])
        accession = accession_by_period_end[(ticker, period_end)]
        for metric, default_priorities in config.metric_concepts.items():
            priorities = (
                config.revenue_priority_by_ticker[ticker]
                if metric == "revenue"
                else default_priorities
            )
            concept, candidates = _concept_candidates(facts, accession, metric, priorities)
            if metric == "inventory":
                selected = _choose_reconciled(
                    [row for row in candidates if row["duration_class"] == "instant"],
                    f"{ticker} {fiscal_year}Q{fiscal_quarter} {metric}",
                )
                value = Decimal(str(selected["value_raw"]))
                formula = "direct_instant"
                operands = [str(selected["fact_id"])]
            elif metric in FLOW_METRICS:
                direct = [
                    row
                    for row in candidates
                    if row["duration_class"] == "quarter"
                    and row["period_start"] == period_start
                    and row["period_end"] == period_end
                ]
                expected_class = {
                    1: "quarter",
                    2: "half_ytd",
                    3: "nine_month_ytd",
                    4: "annual",
                }[fiscal_quarter]
                cumulative = _choose_reconciled(
                    [row for row in candidates if row["duration_class"] == expected_class],
                    f"{ticker} {fiscal_year}Q{fiscal_quarter} {metric} cumulative",
                )
                if direct:
                    selected = _choose_reconciled(
                        direct, f"{ticker} {fiscal_year}Q{fiscal_quarter} {metric} direct"
                    )
                    value = Decimal(str(selected["value_raw"]))
                    formula = "direct_quarter"
                    operands = [str(selected["fact_id"])]
                elif fiscal_quarter == 1:
                    value = Decimal(str(cumulative["value_raw"]))
                    formula = "direct_quarter"
                    operands = [str(cumulative["fact_id"])]
                else:
                    previous = previous_cumulative.get((company_id, metric))
                    if previous is None or int(previous["fiscal_year"]) != fiscal_year:
                        value = None
                        formula = "unresolved_missing_prior_cumulative"
                        operands = [str(cumulative["fact_id"])]
                    else:
                        value = Decimal(str(cumulative["value_raw"])) - Decimal(
                            str(previous["value_raw"])
                        )
                        formula = "cumulative_minus_prior_cumulative_v1"
                        operands = [str(cumulative["fact_id"]), str(previous["fact_id"])]
                previous_cumulative[(company_id, metric)] = {
                    **cumulative,
                    "fiscal_year": fiscal_year,
                }
            else:
                raise ValueError(f"Unsupported canonical metric: {metric}")
            if (
                value is not None
                and metric in {"revenue", "inventory", "capital_expenditure"}
                and value < 0
            ):
                raise ValueError(
                    f"Unexpected negative {metric} for {ticker} {fiscal_year}Q{fiscal_quarter}"
                )
            results.append(
                {
                    "schema_version": config.schema_version,
                    "company_id": company_id,
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "fiscal_quarter": fiscal_quarter,
                    "period_end": period_end,
                    "metric": metric,
                    "value": str(value) if value is not None else None,
                    "unit": "USD",
                    "concept_selected": concept,
                    "formula": formula,
                    "operand_fact_ids": operands,
                    "accession_number": accession,
                }
            )
    output = pl.DataFrame(results).sort("company_id", "fiscal_year", "fiscal_quarter", "metric")
    expected_rows = periods.height * len(config.metric_concepts)
    if output.height != expected_rows:
        raise ValueError(f"Expected {expected_rows} canonical values, got {output.height}")
    key_columns = ["company_id", "fiscal_year", "fiscal_quarter", "metric"]
    if output.select(key_columns).unique().height != output.height:
        raise ValueError("Canonical financial value keys are not unique")
    output_path = repo_root / config.output_path
    manifest_path = repo_root / config.manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_parquet(output_path, compression="zstd")
    formula_counts = {
        str(row["formula"]): row["len"]
        for row in output.group_by("formula").len().sort("formula").iter_rows(named=True)
    }
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "company_count": output["company_id"].n_unique(),
        "fiscal_period_count": periods.height,
        "metric_count": len(config.metric_concepts),
        "canonical_value_count": output.height,
        "resolved_value_count": output.filter(pl.col("value").is_not_null()).height,
        "unresolved_value_count": output.filter(pl.col("value").is_null()).height,
        "formula_counts": formula_counts,
        "output_sha256": _sha256(output_path),
        "interpretation": "Canonical thin-slice values; filing-sample reconciliation remains open.",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
