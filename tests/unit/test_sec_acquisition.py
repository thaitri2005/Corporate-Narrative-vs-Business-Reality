from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import httpx

from cnbr.config import SecSpikeConfig
from cnbr.sources.sec import SecClient
from cnbr.sources.sec_acquisition import run_sec_spike


def test_sec_spike_is_atomic_hashed_and_resumable(tmp_path: Path) -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/submissions/CIK0000021344.json":
            payload = {
                "filings": {
                    "files": [
                        {
                            "name": "CIK0000021344-submissions-001.json",
                            "filingFrom": "2010-01-01",
                            "filingTo": "2018-01-01",
                        },
                        {
                            "name": "CIK0000021344-submissions-002.json",
                            "filingFrom": "2000-01-01",
                            "filingTo": "2009-12-31",
                        },
                    ]
                }
            }
        else:
            payload = {"source": request.url.path}
        return httpx.Response(200, json=payload, request=request)

    config = SecSpikeConfig.model_validate(
        {
            "companies": [{"cik": "21344", "ticker": "KO", "reason": "calendar-year fixture"}],
            "max_workers": 2,
            "requests_per_second": 8,
            "max_attempts": 2,
            "study_start": "2017-01-01",
            "study_end": "2024-12-31",
            "output_dir": "data/raw/sec/test",
            "manifest_path": "data/raw/sec/test.manifest.json",
        }
    )
    with SecClient(
        "CNBR Research team@organization.org",
        transport=httpx.MockTransport(handler),
        sleeper=lambda _: None,
    ) as client:
        first = run_sec_spike(
            config, tmp_path, "CNBR Research team@organization.org", client=client
        )
        second = run_sec_spike(
            config, tmp_path, "CNBR Research team@organization.org", client=client
        )

    assert len(requests) == 3
    assert first["artifact_count"] == 3
    assert second["artifact_count"] == 3
    artifacts = cast(list[dict[str, object]], second["artifacts"])
    assert {artifact["disposition"] for artifact in artifacts} == {"cached"}
    assert not list(tmp_path.rglob("*.tmp"))
    manifest = json.loads(
        (tmp_path / "data/raw/sec/test.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["error_count"] == 0
    assert manifest["total_bytes"] > 0
