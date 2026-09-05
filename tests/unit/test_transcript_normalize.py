from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.config import TranscriptNormalizeConfig
from cnbr.transcripts import normalize_transcripts


def test_transcript_normalization_preserves_order_roles_and_ids(tmp_path: Path) -> None:
    input_path = tmp_path / "data/interim/calls.parquet"
    universe_path = tmp_path / "data/curated/universe.parquet"
    input_path.parent.mkdir(parents=True)
    universe_path.parent.mkdir(parents=True)
    repeated = "this sufficiently long source segment is repeated exactly for duplicate checking"
    pl.DataFrame(
        {
            "ticker": ["KO"],
            "date": ["2024-01-01"],
            "participants": [
                [
                    {
                        "description": "Chief Executive Officer",
                        "name": "Alex A.",
                        "position": "Executive",
                    }
                ]
            ],
            "prepared_remarks": [[{"name": "Alex A.", "speech": [repeated]}]],
            "questions_and_answers": [
                [
                    {"name": "Operator", "speech": [repeated]},
                    {"name": "Jane -- Bank -- Analyst", "speech": ["short response here"]},
                ]
            ],
        }
    ).write_parquet(input_path)
    pl.DataFrame({"ticker": ["KO"], "company_id": ["sec-cik-0000021344"]}).write_parquet(
        universe_path
    )
    config = TranscriptNormalizeConfig(
        source_revision="fixture",
        input_path=Path("data/interim/calls.parquet"),
        universe_path=Path("data/curated/universe.parquet"),
        calls_path=Path("data/curated/canonical_calls.parquet"),
        participants_path=Path("data/curated/participants.parquet"),
        utterances_path=Path("data/curated/utterances.parquet"),
        manifest_path=Path("data/curated/manifest.json"),
        role_by_position={"Executive": "executive"},
        duplicate_minimum_words=5,
    )

    first = normalize_transcripts(config, tmp_path)
    first_ids = pl.read_parquet(tmp_path / config.utterances_path)["utterance_id"].to_list()
    second = normalize_transcripts(config, tmp_path)
    utterances = pl.read_parquet(tmp_path / config.utterances_path)
    participants = pl.read_parquet(tmp_path / config.participants_path)

    assert first["utterance_count"] == 3
    assert second["output_sha256"] == first["output_sha256"]
    assert utterances["utterance_id"].to_list() == first_ids
    assert utterances["sequence_no"].to_list() == [0, 1, 2]
    assert utterances["speaker_role"].to_list() == ["executive", "operator", "analyst"]
    assert utterances["is_exact_duplicate"].to_list() == [True, True, False]
    assert participants.height == 3
    assert participants.filter(~pl.col("source_listed")).height == 2
    assert set(utterances["participant_id"].to_list()).issubset(
        set(participants["participant_id"].to_list())
    )
