from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from cnbr.config import SecFilingIndexConfig
from cnbr.financials.filing_index import build_filing_index


def _columnar(
    accessions: list[str], forms: list[str], report_dates: list[str]
) -> dict[str, object]:
    count = len(accessions)
    return {
        "accessionNumber": accessions,
        "filingDate": ["2024-02-01"] * count,
        "reportDate": report_dates,
        "acceptanceDateTime": ["2024-02-01T12:00:00.000Z"] * count,
        "form": forms,
        "primaryDocument": ["report.htm"] * count,
    }


def _config() -> SecFilingIndexConfig:
    return SecFilingIndexConfig.model_validate(
        {
            "study_start": "2017-01-01",
            "study_end": "2024-12-31",
            "input_dir": "data/raw/sec/sample",
            "output_path": "data/curated/filings.parquet",
            "summary_path": "reports/filings.json",
        }
    )


def test_filing_index_combines_recent_and_history(tmp_path: Path) -> None:
    company = tmp_path / "data/raw/sec/sample/0000021344"
    history = company / "submissions-history"
    history.mkdir(parents=True)
    recent = _columnar(["recent-1", "ignored-8k"], ["10-K", "8-K"], ["2024-12-31"] * 2)
    main = {
        "name": "Fixture Company",
        "tickers": ["FIX"],
        "fiscalYearEnd": "1231",
        "filings": {"recent": recent},
    }
    (company / "submissions.json").write_text(json.dumps(main), encoding="utf-8")
    old = _columnar(["old-1", "recent-1"], ["10-Q", "10-K"], ["2017-03-31", "2024-12-31"])
    (history / "CIK0000021344-submissions-001.json").write_text(json.dumps(old), encoding="utf-8")

    summary = build_filing_index(_config(), tmp_path)

    frame = pl.read_parquet(tmp_path / "data/curated/filings.parquet")
    assert frame["accession_number"].to_list() == ["old-1", "recent-1"]
    assert summary["filing_count"] == 2
    assert summary["company_count"] == 1


def test_filing_index_rejects_unequal_source_columns(tmp_path: Path) -> None:
    company = tmp_path / "data/raw/sec/sample/0000021344"
    company.mkdir(parents=True)
    broken = _columnar(["one"], ["10-K"], ["2024-12-31"])
    broken["form"] = []
    main = {
        "name": "Fixture Company",
        "tickers": ["FIX"],
        "fiscalYearEnd": "1231",
        "filings": {"recent": broken},
    }
    (company / "submissions.json").write_text(json.dumps(main), encoding="utf-8")

    with pytest.raises(ValueError, match="unequal lengths"):
        build_filing_index(_config(), tmp_path)
