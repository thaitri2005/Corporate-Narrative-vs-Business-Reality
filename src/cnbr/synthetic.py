from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import polars as pl
import structlog

from cnbr.config import SyntheticConfig
from cnbr.run_context import make_run_context, sha256_file

LOGGER = structlog.get_logger(__name__)

REQUIRED_COLUMNS: Final[set[str]] = {
    "call_id",
    "company_id",
    "fiscal_year",
    "fiscal_quarter",
    "sequence_no",
    "section",
    "speaker_role",
    "text",
    "pricing_score",
    "cost_score",
    "future_revenue_growth",
}


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_synthetic_pipeline(config: SyntheticConfig, repo_root: Path) -> dict[str, object]:
    input_path = _resolve(repo_root, config.input_path)
    interim_path = _resolve(repo_root, config.interim_path)
    feature_path = _resolve(repo_root, config.feature_path)
    summary_path = _resolve(repo_root, config.summary_path)
    manifest_path = _resolve(repo_root, config.run_manifest_path)

    raw = pl.read_ndjson(input_path)
    missing = REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise ValueError(f"Synthetic input is missing required columns: {sorted(missing)}")

    normalized = raw.with_columns(
        pl.col("text").str.split(" ").list.len().cast(pl.UInt32).alias("token_count"),
        pl.col("fiscal_year").cast(pl.Int32),
        pl.col("fiscal_quarter").cast(pl.Int8),
        pl.col("sequence_no").cast(pl.Int32),
    ).sort(["company_id", "fiscal_year", "fiscal_quarter", "sequence_no"])
    duplicate_keys = normalized.select(
        pl.struct(["call_id", "sequence_no"]).is_duplicated().any()
    ).item()
    if duplicate_keys:
        raise ValueError("Synthetic input contains duplicate call/sequence keys")
    if normalized.filter(~pl.col("fiscal_quarter").is_between(1, 4)).height:
        raise ValueError("Synthetic input contains an invalid fiscal quarter")

    interim_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.write_parquet(interim_path, compression="zstd")

    management = normalized.filter(pl.col("speaker_role") == "executive")
    features = (
        management.group_by(["company_id", "fiscal_year", "fiscal_quarter"])
        .agg(
            pl.col("pricing_score").mean().alias("pricing_intensity"),
            pl.col("cost_score").mean().alias("cost_intensity"),
            pl.col("future_revenue_growth").first(),
            pl.col("token_count").sum().alias("management_token_count"),
        )
        .sort(["company_id", "fiscal_year", "fiscal_quarter"])
        .with_columns(
            pl.col("pricing_intensity").diff().over("company_id").alias("pricing_change"),
            pl.col("cost_intensity").diff().over("company_id").alias("cost_change"),
        )
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    features.write_parquet(feature_path, compression="zstd")

    summary = features.select(
        pl.len().alias("company_quarters"),
        pl.col("company_id").n_unique().alias("companies"),
        pl.col("pricing_intensity").mean().alias("mean_pricing_intensity"),
        pl.col("cost_intensity").mean().alias("mean_cost_intensity"),
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.write_csv(summary_path)

    context = make_run_context(
        repo_root=repo_root,
        command="cnbr synthetic-run",
        config_hash=config.content_hash(),
        input_hash=sha256_file(input_path),
        seed=config.seed,
    )
    output_hashes = {
        "interim": sha256_file(interim_path),
        "features": sha256_file(feature_path),
        "summary": sha256_file(summary_path),
    }
    manifest: dict[str, object] = {
        **context.to_dict(),
        "schema_version": config.schema_version,
        "input_rows": normalized.height,
        "feature_rows": features.height,
        "output_hashes": output_hashes,
    }
    _write_json(manifest_path, manifest)
    LOGGER.info(
        "synthetic_pipeline_complete",
        run_id=context.run_id,
        input_rows=normalized.height,
        feature_rows=features.height,
    )
    return manifest
