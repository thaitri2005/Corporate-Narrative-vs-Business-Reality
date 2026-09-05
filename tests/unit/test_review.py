from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.config import FiscalReviewConfig
from cnbr.review import build_fiscal_review_packet


def test_review_packet_samples_span_and_does_not_overwrite_checklist(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pl.DataFrame(
        {
            "call_id": ["c1", "c2", "c3", "c4"],
            "ticker": ["TEST"] * 4,
            "call_date": ["2021-01-01", "2021-04-01", "2021-07-01", "2021-10-01"],
            "fiscal_year": [2021] * 4,
            "fiscal_quarter": [1, 2, 3, 4],
            "period_end": ["2020-12-31", "2021-03-31", "2021-06-30", "2021-09-30"],
            "lag_days": [1] * 4,
        }
    ).write_parquet(data / "mappings.parquet")
    pl.DataFrame(
        {
            "call_id": ["c1", "c2", "c3", "c4"],
            "section": ["prepared_remarks"] * 4,
            "text": ["synthetic quarter language"] * 4,
        }
    ).write_parquet(data / "utterances.parquet")
    config = FiscalReviewConfig(
        mappings_path=Path("data/mappings.parquet"),
        utterances_path=Path("data/utterances.parquet"),
        html_path=Path("data/review.html"),
        checklist_path=Path("data/checklist.csv"),
        samples_per_company=3,
        excerpt_characters=500,
    )

    first = build_fiscal_review_packet(config, tmp_path)
    checklist = tmp_path / config.checklist_path
    checklist.write_text("reviewed", encoding="utf-8")
    second = build_fiscal_review_packet(config, tmp_path)

    assert first["sample_count"] == 3
    assert second == first
    assert checklist.read_text(encoding="utf-8") == "reviewed"
    assert "synthetic quarter language" in (tmp_path / config.html_path).read_text(encoding="utf-8")
