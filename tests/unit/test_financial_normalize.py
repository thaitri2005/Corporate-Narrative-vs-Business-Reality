from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.config import FinancialNormalizeConfig
from cnbr.financials import normalize_financial_values


def test_financial_normalization_derives_quarter_from_cumulative_values(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pl.DataFrame(
        {
            "accession_number": ["q1", "q2"],
            "metric": ["revenue", "revenue"],
            "is_current_period": [True, True],
            "is_amendment": [False, False],
            "unit": ["USD", "USD"],
            "concept_raw": ["Revenues", "Revenues"],
            "duration_class": ["quarter", "half_ytd"],
            "period_start": ["2024-01-01", "2024-01-01"],
            "period_end": ["2024-03-31", "2024-06-30"],
            "value_raw": ["100", "150"],
            "fact_id": ["fact-q1", "fact-q2-ytd"],
        }
    ).write_parquet(data / "facts.parquet")
    pl.DataFrame(
        {
            "company_id": ["company-1", "company-1"],
            "fiscal_year": [2024, 2024],
            "fiscal_quarter": [1, 2],
            "period_start": ["2024-01-01", "2024-04-01"],
            "period_end": ["2024-03-31", "2024-06-30"],
        }
    ).write_parquet(data / "periods.parquet")
    pl.DataFrame(
        {
            "ticker": ["TEST", "TEST"],
            "report_date": ["2024-03-31", "2024-06-30"],
            "accession_number": ["q1", "q2"],
            "is_amendment": [False, False],
        }
    ).write_parquet(data / "filings.parquet")
    pl.DataFrame({"company_id": ["company-1"], "ticker": ["TEST"]}).write_parquet(
        data / "universe.parquet"
    )
    config = FinancialNormalizeConfig(
        occurrence_path=Path("data/facts.parquet"),
        fiscal_periods_path=Path("data/periods.parquet"),
        filing_index_path=Path("data/filings.parquet"),
        universe_path=Path("data/universe.parquet"),
        output_path=Path("data/values.parquet"),
        manifest_path=Path("reports/normalize.json"),
        metric_concepts={"revenue": []},
        revenue_priority_by_ticker={"TEST": ["Revenues"]},
    )

    result = normalize_financial_values(config, tmp_path)

    values = pl.read_parquet(tmp_path / config.output_path)
    assert values["value"].to_list() == ["100", "50"]
    assert values["formula"].to_list() == [
        "direct_quarter",
        "cumulative_minus_prior_cumulative_v1",
    ]
    assert values["operand_fact_ids"].to_list()[1] == ["fact-q2-ytd", "fact-q1"]
    assert result["resolved_value_count"] == 2
