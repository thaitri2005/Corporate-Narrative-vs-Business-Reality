from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cnbr.config import SecCompanyConfig, SecSpikeConfig
from cnbr.sources.sec import SEC_BASE_URL, SecClient


@dataclass(frozen=True)
class SecArtifactResult:
    cik: str
    ticker: str
    kind: str
    path: str
    source_url: str
    sha256: str
    bytes: int
    disposition: str


def _validate_json_object(content: bytes, label: str) -> None:
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid JSON for {label}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object for {label}")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _acquire_one(
    client: SecClient,
    company: SecCompanyConfig,
    kind: str,
    output_dir: Path,
) -> SecArtifactResult:
    cik = company.cik.zfill(10)
    relative = Path(cik) / f"{kind}.json"
    destination = output_dir / relative
    if destination.exists():
        content = destination.read_bytes()
        _validate_json_object(content, relative.as_posix())
        if kind == "submissions":
            source_url = f"{SEC_BASE_URL}/submissions/CIK{cik}.json"
        else:
            source_url = f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
        disposition = "cached"
    else:
        source_url, content = client.artifact_bytes(kind, cik)
        _validate_json_object(content, source_url)
        _atomic_write(destination, content)
        disposition = "downloaded"
    return SecArtifactResult(
        cik=cik,
        ticker=company.ticker,
        kind=kind,
        path=relative.as_posix(),
        source_url=source_url,
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        disposition=disposition,
    )


def run_sec_spike(
    config: SecSpikeConfig,
    repo_root: Path,
    user_agent: str,
    *,
    client: SecClient | None = None,
) -> dict[str, object]:
    """Acquire submissions and Company Facts for a bounded, resumable feasibility sample."""
    output_dir = repo_root / config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    sec_client = client or SecClient(
        user_agent,
        requests_per_second=config.requests_per_second,
        max_attempts=config.max_attempts,
    )
    results: list[SecArtifactResult] = []
    errors: list[dict[str, str]] = []
    tasks = [
        (company, kind) for company in config.companies for kind in ("submissions", "companyfacts")
    ]
    try:
        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            futures = {
                executor.submit(_acquire_one, sec_client, company, kind, output_dir): (
                    company,
                    kind,
                )
                for company, kind in tasks
            }
            for future in as_completed(futures):
                company, kind = futures[future]
                try:
                    results.append(future.result())
                except Exception as error:  # preserve all partial failures in the manifest
                    errors.append(
                        {
                            "cik": company.cik.zfill(10),
                            "ticker": company.ticker,
                            "kind": kind,
                            "error_type": type(error).__name__,
                            "message": str(error),
                        }
                    )
    finally:
        if owns_client:
            sec_client.close()

    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "user_agent_sha256": hashlib.sha256(user_agent.encode()).hexdigest(),
        "max_workers": config.max_workers,
        "requests_per_second": config.requests_per_second,
        "artifact_count": len(results),
        "error_count": len(errors),
        "total_bytes": sum(item.bytes for item in results),
        "artifacts": [
            asdict(item) for item in sorted(results, key=lambda item: (item.cik, item.kind))
        ],
        "errors": sorted(errors, key=lambda item: (item["cik"], item["kind"])),
    }
    manifest_path = repo_root / config.manifest_path
    _atomic_write(
        manifest_path,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
    )
    if errors:
        raise RuntimeError(f"SEC spike completed with {len(errors)} failed artifact(s)")
    return manifest
