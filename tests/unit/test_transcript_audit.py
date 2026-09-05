from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from cnbr.config import TranscriptAuditConfig
from cnbr.transcripts import build_transcript_audit


def test_transcript_audit_counts_coverage_and_blank_segments(tmp_path: Path) -> None:
    input_path = tmp_path / "data/interim/calls.parquet"
    input_path.parent.mkdir(parents=True)
    pl.DataFrame(
        {
            "ticker": ["KO", "KO", "PG"],
            "date": ["2023-01-01", "2023-04-01", "2024-01-01"],
            "participants": [[{"name": "A"}], [{"name": "A"}], [{"name": "B"}]],
            "prepared_remarks": [
                [{"name": "A", "speech": ["one two", ""]}],
                [{"name": "A", "speech": ["three words here"]}],
                [{"name": "B", "speech": ["four"]}],
            ],
            "questions_and_answers": [
                [{"name": "A", "speech": ["answer words"]}],
                [{"name": "A", "speech": ["more answer words"]}],
                [{"name": "B", "speech": ["final answer"]}],
            ],
        }
    ).write_parquet(input_path)
    config = TranscriptAuditConfig(
        input_path=Path("data/interim/calls.parquet"),
        call_detail_path=Path("reports/calls.csv"),
        company_summary_path=Path("reports/companies.csv"),
        manifest_path=Path("reports/audit.json"),
        minimum_calls=2,
    )

    result = build_transcript_audit(config, tmp_path)

    assert result["call_count"] == 3
    assert result["eligible_company_count"] == 1
    assert result["companies_with_2024_call"] == 1
    assert result["eligible_companies_with_2024_call"] == 0
    assert result["blank_prepared_segment_count"] == 1
    company = pl.read_csv(tmp_path / "reports/companies.csv")
    assert company.filter(pl.col("ticker") == "KO")["meets_call_threshold"].item()
    manifest = json.loads((tmp_path / "reports/audit.json").read_text(encoding="utf-8"))
    assert manifest["calls_per_company"] == {"maximum": 2, "median": 1.5, "minimum": 1}
