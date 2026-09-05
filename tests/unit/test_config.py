from pathlib import Path

import pytest
from pydantic import ValidationError

from cnbr.config import SecSpikeConfig, SyntheticConfig


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


def test_sec_spike_caps_workers_and_request_rate() -> None:
    payload = {
        "companies": [{"cik": "21344", "ticker": "KO", "reason": "fixture"}],
        "max_workers": 4,
        "requests_per_second": 9,
        "study_start": "2017-01-01",
        "study_end": "2024-12-31",
        "output_dir": "data/raw/sec",
        "manifest_path": "data/raw/sec.manifest.json",
    }
    with pytest.raises(ValidationError):
        SecSpikeConfig.model_validate(payload)
