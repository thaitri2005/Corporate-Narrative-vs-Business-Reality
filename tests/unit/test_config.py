from pathlib import Path

from cnbr.config import SyntheticConfig


def test_config_hash_is_stable() -> None:
    config = SyntheticConfig(
        seed=7,
        input_path=Path("input.jsonl"),
        interim_path=Path("interim.parquet"),
        feature_path=Path("features.parquet"),
        summary_path=Path("summary.csv"),
        run_manifest_path=Path("run.json"),
    )
    assert config.content_hash() == config.content_hash()
    assert len(config.content_hash()) == 64


def test_config_hash_changes_with_seed() -> None:
    first = SyntheticConfig(
        seed=1,
        input_path=Path("input.jsonl"),
        interim_path=Path("interim.parquet"),
        feature_path=Path("features.parquet"),
        summary_path=Path("summary.csv"),
        run_manifest_path=Path("run.json"),
    )
    second = SyntheticConfig(
        seed=2,
        input_path=Path("input.jsonl"),
        interim_path=Path("interim.parquet"),
        feature_path=Path("features.parquet"),
        summary_path=Path("summary.csv"),
        run_manifest_path=Path("run.json"),
    )
    assert first.content_hash() != second.content_hash()
