import json
from pathlib import Path

import polars as pl
import pytest

from cnbr.config import SyntheticConfig
from cnbr.synthetic import run_synthetic_pipeline


@pytest.mark.integration
def test_synthetic_pipeline_is_repeatable(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "synthetic_calls.jsonl"
    config = SyntheticConfig(
        seed=42,
        input_path=fixture,
        interim_path=tmp_path / "interim.parquet",
        feature_path=tmp_path / "features.parquet",
        summary_path=tmp_path / "summary.csv",
        run_manifest_path=tmp_path / "run.json",
    )
    first = run_synthetic_pipeline(config, Path.cwd())
    second = run_synthetic_pipeline(config, Path.cwd())
    assert first["run_id"] == second["run_id"]
    assert first["output_hashes"] == second["output_hashes"]
    features = pl.read_parquet(config.feature_path)
    assert features.height == 4
    assert features.select(pl.col("company_id").n_unique()).item() == 2
    assert features.filter(pl.col("fiscal_quarter") == 1)["pricing_change"].is_null().all()
    manifest = json.loads(config.run_manifest_path.read_text(encoding="utf-8"))
    assert manifest["input_rows"] == 8
    assert manifest["feature_rows"] == 4
