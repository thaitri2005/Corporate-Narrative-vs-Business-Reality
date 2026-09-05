from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import httpx
import polars as pl

from cnbr.config import UniverseConfig

EXPECTED_FIELDS: Final[set[str]] = {
    "Symbol",
    "Security",
    "GICS Sector",
    "GICS Sub-Industry",
    "Headquarters Location",
    "Date added",
    "CIK",
    "Founded",
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def parse_company_universe(content: bytes, config: UniverseConfig) -> pl.DataFrame:
    """Parse and validate an S&P 500 CSV, retaining only the configured sector."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fields = set(reader.fieldnames or [])
    if fields != EXPECTED_FIELDS:
        missing = sorted(EXPECTED_FIELDS - fields)
        unexpected = sorted(fields - EXPECTED_FIELDS)
        raise ValueError(f"Unexpected universe schema; missing={missing}, unexpected={unexpected}")

    records: list[dict[str, str]] = []
    seen_ciks: set[str] = set()
    for raw in reader:
        if raw["GICS Sector"].strip() != config.sector:
            continue
        cik_raw = raw["CIK"].strip()
        if not cik_raw.isdigit():
            raise ValueError(f"Invalid CIK for {raw['Symbol']!r}: {cik_raw!r}")
        cik = cik_raw.zfill(10)
        if cik in seen_ciks:
            raise ValueError(f"Multiple securities map to Consumer Staples CIK {cik}")
        seen_ciks.add(cik)
        row_fingerprint = "|".join(raw[field] for field in sorted(EXPECTED_FIELDS))
        records.append(
            {
                "company_id": f"sec-cik-{cik}",
                "cik": cik,
                "ticker": raw["Symbol"].strip(),
                "legal_name": raw["Security"].strip(),
                "gics_sector": raw["GICS Sector"].strip(),
                "gics_sub_industry": raw["GICS Sub-Industry"].strip(),
                "snapshot_date": config.snapshot_date.isoformat(),
                "source_id": config.source_id,
                "source_row_sha256": hashlib.sha256(row_fingerprint.encode()).hexdigest(),
            }
        )
    if not records:
        raise ValueError(f"No rows found for sector {config.sector!r}")
    return pl.DataFrame(records).sort("cik")


def build_company_universe(
    config: UniverseConfig,
    repo_root: Path,
    *,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    """Acquire, validate, and materialize a hashed point-in-time universe snapshot."""
    owns_client = client is None
    http_client = client or httpx.Client(timeout=30.0, follow_redirects=True)
    try:
        response = http_client.get(
            config.source_url,
            headers={"User-Agent": "cnbr-research/0.1 (company-universe acquisition)"},
        )
        response.raise_for_status()
        content = response.content
    finally:
        if owns_client:
            http_client.close()

    frame = parse_company_universe(content, config)
    raw_path = repo_root / config.raw_path
    curated_path = repo_root / config.curated_path
    manifest_path = repo_root / config.manifest_path
    for path in (raw_path, curated_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(content)
    frame.write_parquet(curated_path)
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "snapshot_date": config.snapshot_date.isoformat(),
        "sector": config.sector,
        "source_id": config.source_id,
        "source_url": config.source_url,
        "source_revision": config.source_revision,
        "source_license": config.source_license,
        "config_sha256": config.content_hash(),
        "raw_sha256": _sha256(content),
        "row_count": frame.height,
        "curated_path": config.curated_path.as_posix(),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
