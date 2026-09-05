from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.config import LexicalBaselineConfig, LexicalTopicDefinition
from cnbr.transcripts import build_lexical_baseline


def test_lexical_baseline_aggregates_local_matches_without_text_output(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pl.DataFrame(
        {
            "call_id": ["call-1"],
            "company_id": ["company-1"],
            "ticker": ["TEST"],
            "fiscal_year": [2024],
            "fiscal_quarter": [1],
            "call_date": ["2024-04-10"],
        }
    ).write_parquet(data / "mappings.parquet")
    pl.DataFrame(
        {
            "call_id": ["call-1", "call-1", "call-1"],
            "quality_flags": [[], [], ["possible_source_footer"]],
            "word_count": [10, 5, 100],
            "speaker_role": ["executive", "executive", "analyst"],
            "section": ["prepared_remarks", "prepared_remarks", "qa"],
            "text": ["Pricing actions are working", "No match here", "guidance boilerplate"],
        },
        schema_overrides={"quality_flags": pl.List(pl.String)},
    ).write_parquet(data / "utterances.parquet")
    config = LexicalBaselineConfig(
        taxonomy_version="test",
        utterances_path=Path("data/utterances.parquet"),
        call_mappings_path=Path("data/mappings.parquet"),
        output_path=Path("data/features.parquet"),
        manifest_path=Path("reports/lexical.json"),
        excluded_quality_flags=["possible_source_footer"],
        views=["management_prepared", "analyst_qa"],
        topics=[
            LexicalTopicDefinition(topic_id="pricing", display_name="Pricing", patterns=["pricing"])
        ],
    )

    result = build_lexical_baseline(config, tmp_path)

    output = pl.read_parquet(tmp_path / config.output_path)
    pricing = output.filter(pl.col("view") == "management_prepared").row(0, named=True)
    analyst = output.filter(pl.col("view") == "analyst_qa").row(0, named=True)
    assert result["observation_count"] == 2
    assert pricing["eligible_word_count"] == 15
    assert pricing["matched_word_count"] == 10
    assert pricing["matched_word_share"] == 10 / 15
    assert analyst["eligible_word_count"] == 0
    assert analyst["matched_word_share"] is None
