from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
import polars as pl

from cnbr.config import StruxIngestionConfig, StruxSourceFile

EXPECTED_COLUMNS = {
    "ticker",
    "date",
    "participants",
    "prepared_remarks",
    "questions_and_answers",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download_source(
    source: StruxSourceFile,
    repo_root: Path,
    client: httpx.Client,
) -> tuple[Path, str]:
    destination = repo_root / source.raw_path
    if destination.exists():
        actual = _sha256_file(destination)
        if actual != source.sha256:
            raise ValueError(f"Existing STRUX source hash mismatch: {source.raw_path}")
        return destination, "cached"

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    digest = hashlib.sha256()
    try:
        with client.stream("GET", source.url) as response:
            response.raise_for_status()
            with temporary.open("wb") as stream:
                for block in response.iter_bytes(chunk_size=1024 * 1024):
                    digest.update(block)
                    stream.write(block)
        actual = digest.hexdigest()
        if actual != source.sha256:
            raise ValueError(f"Downloaded STRUX source hash mismatch: {source.raw_path}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination, "downloaded"


def ingest_strux_subset(
    config: StruxIngestionConfig,
    repo_root: Path,
    *,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    """Acquire verified full-split shards and retain the approved universe locally."""
    owns_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(120.0, connect=30.0),
        follow_redirects=True,
        headers={"User-Agent": "cnbr-personal-research/0.1"},
    )
    raw_paths: list[Path] = []
    source_records: list[dict[str, object]] = []
    try:
        for source in config.sources:
            path, disposition = _download_source(source, repo_root, http_client)
            raw_paths.append(path)
            source_records.append(
                {
                    "url": source.url,
                    "path": source.raw_path.as_posix(),
                    "sha256": source.sha256,
                    "bytes": path.stat().st_size,
                    "disposition": disposition,
                }
            )
    finally:
        if owns_client:
            http_client.close()

    for path in raw_paths:
        columns = set(pl.read_parquet_schema(path))
        if columns != EXPECTED_COLUMNS:
            raise ValueError(
                f"Unexpected STRUX schema in {path.name}; "
                f"missing={sorted(EXPECTED_COLUMNS - columns)}, "
                f"unexpected={sorted(columns - EXPECTED_COLUMNS)}"
            )
    universe = pl.read_parquet(repo_root / config.universe_path)
    eligible_tickers = sorted(universe["ticker"].unique().to_list())
    subset = (
        pl.scan_parquet(raw_paths)
        .filter(pl.col("ticker").is_in(eligible_tickers))
        .collect()
        .sort("ticker", "date")
    )
    if subset.is_empty():
        raise ValueError("STRUX filter produced no Consumer Staples transcripts")
    duplicates = subset.group_by("ticker", "date").len().filter(pl.col("len") > 1)
    company_counts = subset.group_by("ticker").len()
    count_values = cast(list[int], company_counts["len"].to_list())
    minimum_calls = min(count_values)
    maximum_calls = max(count_values)
    sorted_counts = sorted(count_values)
    midpoint = len(sorted_counts) // 2
    median_calls = (
        float(sorted_counts[midpoint])
        if len(sorted_counts) % 2
        else (sorted_counts[midpoint - 1] + sorted_counts[midpoint]) / 2
    )
    empty_sections = subset.select(
        pl.col("participants").list.len().eq(0).sum().alias("participants"),
        pl.col("prepared_remarks").list.len().eq(0).sum().alias("prepared_remarks"),
        pl.col("questions_and_answers").list.len().eq(0).sum().alias("questions_and_answers"),
    ).row(0, named=True)
    output_path = repo_root / config.output_path
    manifest_path = repo_root / config.manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    subset.write_parquet(output_path, compression="zstd")
    present_tickers = sorted(subset["ticker"].unique().to_list())
    missing_tickers = sorted(set(eligible_tickers) - set(present_tickers))
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "source_revision": config.source_revision,
        "rights_policy": config.rights_policy,
        "config_sha256": config.content_hash(),
        "sources": source_records,
        "eligible_ticker_count": len(eligible_tickers),
        "present_ticker_count": len(present_tickers),
        "missing_tickers": missing_tickers,
        "transcript_count": subset.height,
        "duplicate_ticker_date_count": duplicates.height,
        "first_call_date": subset["date"].min(),
        "last_call_date": subset["date"].max(),
        "calls_per_company": {
            "minimum": minimum_calls,
            "median": median_calls,
            "maximum": maximum_calls,
            "companies_with_at_least_12": company_counts.filter(pl.col("len") >= 12).height,
            "companies_with_at_least_16": company_counts.filter(pl.col("len") >= 16).height,
        },
        "empty_section_counts": empty_sections,
        "output_path": config.output_path.as_posix(),
        "output_sha256": _sha256_file(output_path),
        "output_bytes": output_path.stat().st_size,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
