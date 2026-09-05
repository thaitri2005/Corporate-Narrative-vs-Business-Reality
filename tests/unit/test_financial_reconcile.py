from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.config import FinancialReconciliationConfig
from cnbr.financials import reconcile_financial_values


def test_financial_reconciliation_checks_direct_and_derived_values(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pl.DataFrame(
        {"fact_id": ["direct", "current", "prior"], "value_raw": ["10", "40", "25"]}
    ).write_parquet(data / "facts.parquet")
    pl.DataFrame(
        {
            "company_id": ["company", "company", "company"],
            "ticker": ["TEST", "TEST", "TEST"],
            "fiscal_year": [2024, 2024, 2024],
            "fiscal_quarter": [1, 2, 3],
            "metric": ["revenue", "revenue", "capital_expenditure"],
            "formula": [
                "direct_quarter",
                "cumulative_minus_prior_cumulative_v1",
                "unresolved_missing_prior_cumulative",
            ],
            "operand_fact_ids": [["direct"], ["current", "prior"], ["current"]],
            "value": ["10", "15", None],
        },
        schema_overrides={"operand_fact_ids": pl.List(pl.String)},
    ).write_parquet(data / "values.parquet")
    config = FinancialReconciliationConfig(
        values_path=Path("data/values.parquet"),
        occurrence_path=Path("data/facts.parquet"),
        detail_path=Path("reports/sample.csv"),
        manifest_path=Path("reports/manifest.json"),
    )

    result = reconcile_financial_values(config, tmp_path)

    assert result["audited_value_count"] == 3
    assert result["status_counts"] == {"expected_unresolved": 1, "pass": 2}
    assert (tmp_path / config.detail_path).exists()
