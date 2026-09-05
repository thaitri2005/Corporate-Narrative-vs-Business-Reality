from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from cnbr.config import PanelBuildConfig


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _next_quarter(year: int, quarter: int) -> tuple[int, int]:
    return (year + 1, 1) if quarter == 4 else (year, quarter + 1)


def build_thin_slice_panel(config: PanelBuildConfig, repo_root: Path) -> dict[str, object]:
    """Join mapped narrative structure to current and next-quarter financial features."""
    narrative_path = repo_root / config.narrative_path
    financial_path = repo_root / config.financial_path
    narrative = pl.read_parquet(narrative_path)
    financial = pl.read_parquet(financial_path)
    financial_by_period: dict[tuple[str, int, int], dict[str, str]] = {}
    for row in financial.iter_rows(named=True):
        key = (str(row["company_id"]), int(row["fiscal_year"]), int(row["fiscal_quarter"]))
        financial_by_period.setdefault(key, {})[str(row["metric"])] = str(row["value"])
    rows: list[dict[str, object]] = []
    for narrative_row in narrative.iter_rows(named=True):
        company_id = str(narrative_row["company_id"])
        year = int(narrative_row["fiscal_year"])
        quarter = int(narrative_row["fiscal_quarter"])
        current = financial_by_period.get((company_id, year, quarter), {})
        next_year, next_quarter = _next_quarter(year, quarter)
        lead = financial_by_period.get((company_id, next_year, next_quarter), {})
        output_row = dict(narrative_row)
        for metric in config.current_financial_metrics:
            output_row[f"current_{metric}"] = current.get(metric)
        for metric in config.lead_outcome_metrics:
            output_row[f"lead1_{metric}"] = lead.get(metric)
        output_row["lead1_fiscal_year"] = next_year
        output_row["lead1_fiscal_quarter"] = next_quarter
        rows.append(output_row)
    panel = pl.DataFrame(rows).sort("company_id", "fiscal_year", "fiscal_quarter")
    key_columns = ["company_id", "fiscal_year", "fiscal_quarter"]
    if panel.select(key_columns).unique().height != panel.height:
        raise ValueError("Analytical panel keys are not unique")
    output_path = repo_root / config.output_path
    manifest_path = repo_root / config.manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    panel.write_parquet(output_path, compression="zstd")
    lead_coverage = {
        metric: panel.filter(pl.col(f"lead1_{metric}").is_not_null()).height
        for metric in config.lead_outcome_metrics
    }
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "observation_count": panel.height,
        "company_count": panel["company_id"].n_unique(),
        "lead_outcome_coverage": lead_coverage,
        "narrative_sha256": _sha256(narrative_path),
        "financial_sha256": _sha256(financial_path),
        "output_sha256": _sha256(output_path),
        "interpretation": "Join/lag artifact only; no association or model has been estimated.",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
