from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.config import AnnotationPilotConfig
from cnbr.transcripts import build_annotation_pilot


def test_annotation_pilot_writes_restricted_tasks_and_text_free_manifest(tmp_path: Path) -> None:
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
            "call_id": ["call-1"],
            "sequence_no": [0],
            "quality_flags": [[]],
            "speaker_role": ["executive"],
            "section": ["prepared_remarks"],
            "text": ["Synthetic pricing example"],
        },
        schema_overrides={"quality_flags": pl.List(pl.String)},
    ).write_parquet(data / "utterances.parquet")
    lexical = tmp_path / "lexical.yaml"
    lexical.write_text(
        "taxonomy_version: test\nutterances_path: data/utterances.parquet\n"
        "call_mappings_path: data/mappings.parquet\noutput_path: data/out.parquet\n"
        "manifest_path: reports/out.json\nexcluded_quality_flags: []\n"
        "views: [management_prepared]\n"
        "topics:\n  - topic_id: pricing\n    display_name: Pricing\n    patterns: [pricing]\n",
        encoding="utf-8",
    )
    config = AnnotationPilotConfig(
        utterances_path=Path("data/utterances.parquet"),
        call_mappings_path=Path("data/mappings.parquet"),
        lexical_config_path=Path("lexical.yaml"),
        tasks_path=Path("data/review/tasks.json"),
        html_path=Path("data/review/tasks.html"),
        manifest_path=Path("reports/manifest.json"),
        samples_per_topic=1,
        excluded_quality_flags=[],
    )

    result = build_annotation_pilot(config, tmp_path)

    assert result["task_count"] == 1
    assert result["release_class"] == "restricted-local-annotation-tasks"
    assert (tmp_path / config.tasks_path).exists()
    assert (tmp_path / config.html_path).exists()
    assert "Synthetic pricing example" not in (tmp_path / config.manifest_path).read_text()
