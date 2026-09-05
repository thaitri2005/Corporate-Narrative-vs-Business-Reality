from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.config import NarrativeFeatureConfig
from cnbr.transcripts import build_narrative_structure_features


def test_narrative_features_respect_roles_sections_and_exclusions(tmp_path: Path) -> None:
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
            "word_count": [80, 20, 10],
            "speaker_role": ["executive", "analyst", "analyst"],
            "section": ["prepared_remarks", "qa", "qa"],
        },
        schema_overrides={"quality_flags": pl.List(pl.String)},
    ).write_parquet(data / "utterances.parquet")
    config = NarrativeFeatureConfig(
        utterances_path=Path("data/utterances.parquet"),
        call_mappings_path=Path("data/mappings.parquet"),
        output_path=Path("data/features.parquet"),
        manifest_path=Path("reports/features.json"),
        excluded_quality_flags=["possible_source_footer"],
    )

    result = build_narrative_structure_features(config, tmp_path)

    features = pl.read_parquet(tmp_path / config.output_path).row(0, named=True)
    assert features["eligible_word_count"] == 100
    assert features["management_prepared_share"] == 0.8
    assert features["analyst_qa_share"] == 0.2
    assert features["excluded_utterance_count"] == 1
    assert result["observation_count"] == 1
