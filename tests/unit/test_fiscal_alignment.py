from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from cnbr.config import FiscalAlignmentConfig
from cnbr.financials import build_fiscal_alignment


def test_fiscal_alignment_uses_accession_boundaries_and_date_precision(tmp_path: Path) -> None:
    curated = tmp_path / "data/curated"
    raw = tmp_path / "data/raw/sec/0000000001"
    curated.mkdir(parents=True)
    raw.mkdir(parents=True)
    pl.DataFrame(
        {
            "ticker": ["TEST", "TEST"],
            "is_amendment": [False, False],
            "report_date": ["2024-03-31", "2024-06-30"],
            "accession_number": ["accn-q1", "accn-q2"],
            "accepted_at": ["2024-04-20T10:00:00Z", "2024-07-20T10:00:00Z"],
        }
    ).write_parquet(curated / "filings.parquet")
    pl.DataFrame(
        {
            "ticker": ["TEST"],
            "company_id": ["sec-cik-0000000001"],
            "cik": ["0000000001"],
        }
    ).write_parquet(curated / "universe.parquet")
    pl.DataFrame(
        {
            "call_id": ["call-q2"],
            "ticker": ["TEST"],
            "call_date": ["2024-07-10"],
        }
    ).write_parquet(curated / "calls.parquet")
    company_facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "start": "2024-01-01",
                                "end": "2024-03-31",
                                "fy": 2024,
                                "fp": "Q1",
                                "accn": "accn-q1",
                            },
                            {
                                "start": "2024-01-01",
                                "end": "2024-06-30",
                                "fy": 2024,
                                "fp": "Q2",
                                "accn": "accn-q2",
                            },
                            {
                                "start": "2024-04-01",
                                "end": "2024-06-30",
                                "fy": 2024,
                                "fp": "Q2",
                                "accn": "accn-q2",
                            },
                        ]
                    }
                }
            }
        }
    }
    (raw / "companyfacts.json").write_text(json.dumps(company_facts), encoding="utf-8")
    config = FiscalAlignmentConfig(
        companies=["TEST"],
        filing_index_path=Path("data/curated/filings.parquet"),
        calls_path=Path("data/curated/calls.parquet"),
        universe_path=Path("data/curated/universe.parquet"),
        sec_raw_dir=Path("data/raw/sec"),
        fiscal_periods_path=Path("data/curated/periods.parquet"),
        call_mappings_path=Path("data/curated/mappings.parquet"),
        manifest_path=Path("reports/alignment.json"),
        period_boundary_concepts=["Revenues"],
    )

    result = build_fiscal_alignment(config, tmp_path)

    periods = pl.read_parquet(tmp_path / config.fiscal_periods_path)
    assert result["fiscal_period_count"] == 2
    assert result["mapped_call_count"] == 1
    assert periods["fiscal_quarter"].to_list() == [1, 2]
    assert periods["period_start"].to_list() == ["2024-01-01", "2024-04-01"]
    assert periods["call_time_precision"].to_list() == [None, "date"]
