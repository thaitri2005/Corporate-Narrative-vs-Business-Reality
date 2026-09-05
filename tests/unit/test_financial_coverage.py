from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cnbr.config import SecCoverageConfig
from cnbr.financials.coverage import build_concept_coverage


def test_build_concept_coverage_counts_unique_fiscal_periods(tmp_path: Path) -> None:
    company_dir = tmp_path / "data/raw/sec/sample/0000021344"
    company_dir.mkdir(parents=True)
    facts = {
        "entityName": "Fixture Company",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"fy": 2023, "fp": "Q1", "form": "10-Q"},
                            {"fy": 2023, "fp": "Q1", "form": "10-Q/A"},
                            {"fy": 2023, "fp": "FY", "form": "10-K"},
                            {"fy": 2016, "fp": "FY", "form": "10-K"},
                        ]
                    }
                }
            }
        },
    }
    (company_dir / "companyfacts.json").write_text(json.dumps(facts), encoding="utf-8")
    (company_dir / "submissions.json").write_text(
        json.dumps({"tickers": ["FIX"]}), encoding="utf-8"
    )
    config = SecCoverageConfig.model_validate(
        {
            "start_fiscal_year": 2017,
            "end_fiscal_year": 2024,
            "input_dir": "data/raw/sec/sample",
            "detail_path": "reports/detail.csv",
            "summary_path": "reports/summary.json",
            "concepts": {
                "revenue": {"concepts": ["Revenues"], "expected_periods": 32},
                "gross_profit": {"concepts": ["GrossProfit"], "expected_periods": 32},
            },
        }
    )

    summary = build_concept_coverage(config, tmp_path)

    metrics = cast(list[dict[str, object]], summary["metrics"])
    revenue = next(item for item in metrics if item["metric"] == "revenue")
    gross_profit = next(item for item in metrics if item["metric"] == "gross_profit")
    assert revenue["companies_with_coverage"] == 1
    assert revenue["maximum_coverage_ratio"] == 0.0625
    assert gross_profit["companies_with_coverage"] == 0
    detail = (tmp_path / "reports/detail.csv").read_text(encoding="utf-8")
    assert "Revenues" in detail
