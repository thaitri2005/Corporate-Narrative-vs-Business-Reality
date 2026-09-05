from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.config import FinancialFeatureConfig
from cnbr.financials import build_financial_features


def test_financial_features_compute_ratios_and_same_quarter_yoy(tmp_path: Path) -> None:
    input_path = tmp_path / "data/values.parquet"
    input_path.parent.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    values = {
        2023: {
            "revenue": "100",
            "operating_income": "10",
            "inventory": "20",
            "capital_expenditure": "5",
        },
        2024: {
            "revenue": "120",
            "operating_income": "18",
            "inventory": "22",
            "capital_expenditure": "6",
        },
    }
    for year, metrics in values.items():
        for metric, value in metrics.items():
            rows.append(
                {
                    "company_id": "company-1",
                    "ticker": "TEST",
                    "fiscal_year": year,
                    "fiscal_quarter": 1,
                    "period_end": f"{year}-03-31",
                    "metric": metric,
                    "value": value,
                }
            )
    pl.DataFrame(rows).write_parquet(input_path)
    config = FinancialFeatureConfig(
        input_path=Path("data/values.parquet"),
        output_path=Path("data/features.parquet"),
        manifest_path=Path("reports/features.json"),
    )

    result = build_financial_features(config, tmp_path)

    features = pl.read_parquet(tmp_path / config.output_path)
    current = features.filter(pl.col("fiscal_year") == 2024)
    feature_values = dict(current.select("metric", "value").iter_rows())
    assert feature_values["operating_margin"] == "0.15"
    assert feature_values["capital_expenditure_to_revenue"] == "0.05"
    assert feature_values["revenue_yoy"] == "0.2"
    assert feature_values["inventory_yoy"] == "0.1"
    assert result["feature_count"] == 14
