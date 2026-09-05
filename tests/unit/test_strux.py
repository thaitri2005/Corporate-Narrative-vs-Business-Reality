from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import httpx
import polars as pl

from cnbr.config import StruxIngestionConfig
from cnbr.sources.strux import ingest_strux_subset


def _parquet_bytes(path: Path, rows: list[dict[str, object]]) -> bytes:
    pl.DataFrame(rows).write_parquet(path)
    return path.read_bytes()


def test_strux_ingestion_is_verified_filtered_and_resumable(tmp_path: Path) -> None:
    universe_path = tmp_path / "data/curated/universe.parquet"
    universe_path.parent.mkdir(parents=True)
    pl.DataFrame({"ticker": ["KO", "PG"]}).write_parquet(universe_path)

    first_bytes = _parquet_bytes(
        tmp_path / "first.fixture.parquet",
        [
            {
                "ticker": "KO",
                "date": "2024-01-01",
                "participants": ["fixture"],
                "prepared_remarks": ["fixture"],
                "questions_and_answers": ["fixture"],
            },
            {
                "ticker": "MSFT",
                "date": "2024-01-02",
                "participants": ["fixture"],
                "prepared_remarks": ["fixture"],
                "questions_and_answers": ["fixture"],
            },
        ],
    )
    second_bytes = _parquet_bytes(
        tmp_path / "second.fixture.parquet",
        [
            {
                "ticker": "KO",
                "date": "2024-04-01",
                "participants": ["fixture"],
                "prepared_remarks": ["fixture"],
                "questions_and_answers": ["fixture"],
            }
        ],
    )
    payloads = {"/first.parquet": first_bytes, "/second.parquet": second_bytes}
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, content=payloads[request.url.path], request=request)

    config = StruxIngestionConfig.model_validate(
        {
            "source_revision": "fixture-revision",
            "universe_path": "data/curated/universe.parquet",
            "output_path": "data/interim/strux.parquet",
            "manifest_path": "data/interim/strux.manifest.json",
            "sources": [
                {
                    "url": "https://example.test/first.parquet",
                    "sha256": hashlib.sha256(first_bytes).hexdigest(),
                    "raw_path": "data/raw/strux/first.parquet",
                },
                {
                    "url": "https://example.test/second.parquet",
                    "sha256": hashlib.sha256(second_bytes).hexdigest(),
                    "raw_path": "data/raw/strux/second.parquet",
                },
            ],
        }
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = ingest_strux_subset(config, tmp_path, client=client)
        second = ingest_strux_subset(config, tmp_path, client=client)

    assert requests == ["/first.parquet", "/second.parquet"]
    assert first["transcript_count"] == 2
    assert first["missing_tickers"] == ["PG"]
    sources = cast(list[dict[str, object]], second["sources"])
    assert {source["disposition"] for source in sources} == {"cached"}
    assert pl.read_parquet(tmp_path / "data/interim/strux.parquet")["ticker"].to_list() == [
        "KO",
        "KO",
    ]
    assert not list(tmp_path.rglob("*.tmp"))
    manifest = json.loads(
        (tmp_path / "data/interim/strux.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["rights_policy"] == "personal-local-risk-accepted"
