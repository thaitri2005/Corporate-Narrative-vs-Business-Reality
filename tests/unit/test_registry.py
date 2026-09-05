from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import polars as pl
import pytest

from cnbr.config import UniverseConfig
from cnbr.registry.sp500 import build_company_universe, parse_company_universe


def _config() -> UniverseConfig:
    return UniverseConfig(
        source_id="datahub-sp500",
        source_url="https://example.invalid/constituents.csv",
        source_revision="abc123",
        source_license="ODC-PDDL-1.0",
        snapshot_date=date(2026, 9, 5),
        raw_path=Path("data/raw/universe.csv"),
        curated_path=Path("data/curated/company_universe.parquet"),
        manifest_path=Path("data/curated/company_universe.manifest.json"),
    )


def test_parse_company_universe_filters_and_normalizes() -> None:
    content = Path("tests/fixtures/sp500_sample.csv").read_bytes()

    result = parse_company_universe(content, _config())

    assert result["ticker"].to_list() == ["KO", "PG"]
    assert result["cik"].to_list() == ["0000021344", "0000080424"]
    assert result["gics_sector"].unique().to_list() == ["Consumer Staples"]


def test_parse_company_universe_rejects_schema_drift() -> None:
    with pytest.raises(ValueError, match="Unexpected universe schema"):
        parse_company_universe(b"Symbol,Security\nKO,Coca-Cola\n", _config())


def test_build_company_universe_records_lineage(tmp_path: Path) -> None:
    content = Path("tests/fixtures/sp500_sample.csv").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("cnbr-research/")
        return httpx.Response(200, content=content, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        manifest = build_company_universe(_config(), tmp_path, client=client)

    assert manifest["row_count"] == 2
    assert manifest["source_revision"] == "abc123"
    assert len(str(manifest["raw_sha256"])) == 64
    assert pl.read_parquet(tmp_path / "data/curated/company_universe.parquet").height == 2
    saved = json.loads(
        (tmp_path / "data/curated/company_universe.manifest.json").read_text(encoding="utf-8")
    )
    assert saved["source_license"] == "ODC-PDDL-1.0"
