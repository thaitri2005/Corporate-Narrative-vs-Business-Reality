from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from cnbr.config import FinancialExtractConfig
from cnbr.financials import extract_financial_facts


def test_financial_extract_preserves_occurrences_and_current_status(tmp_path: Path) -> None:
    curated = tmp_path / "data/curated"
    raw = tmp_path / "data/raw/sec/0000000001"
    curated.mkdir(parents=True)
    raw.mkdir(parents=True)
    pl.DataFrame(
        {
            "ticker": ["TEST"],
            "accession_number": ["accn-1"],
            "accepted_at": ["2024-04-20T10:00:00Z"],
            "is_amendment": [False],
            "report_date": ["2024-03-31"],
        }
    ).write_parquet(curated / "filings.parquet")
    pl.DataFrame(
        {"ticker": ["TEST"], "company_id": ["company-1"], "cik": ["0000000001"]}
    ).write_parquet(curated / "universe.parquet")
    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "start": "2023-01-01",
                                "end": "2023-03-31",
                                "val": 90,
                                "accn": "accn-1",
                                "fy": 2024,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2024-04-20",
                            },
                            {
                                "start": "2024-01-01",
                                "end": "2024-03-31",
                                "val": 100,
                                "accn": "accn-1",
                                "fy": 2024,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2024-04-20",
                            },
                        ]
                    }
                }
            }
        }
    }
    (raw / "companyfacts.json").write_text(json.dumps(payload), encoding="utf-8")
    config = FinancialExtractConfig(
        companies=["TEST"],
        filing_index_path=Path("data/curated/filings.parquet"),
        universe_path=Path("data/curated/universe.parquet"),
        sec_raw_dir=Path("data/raw/sec"),
        output_path=Path("data/interim/facts.parquet"),
        manifest_path=Path("reports/extract.json"),
        metric_concepts={"revenue": ["Revenues"]},
    )

    result = extract_financial_facts(config, tmp_path)

    facts = pl.read_parquet(tmp_path / config.output_path)
    assert result["fact_occurrence_count"] == 2
    assert facts["fact_id"].n_unique() == 2
    assert facts["is_current_period"].to_list() == [False, True]
    assert result["metric_coverage"] == [
        {
            "metric": "revenue",
            "base_filings_with_current_usd_fact": 1,
            "base_filing_count": 1,
            "complete": True,
        }
    ]
