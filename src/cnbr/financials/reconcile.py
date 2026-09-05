from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import polars as pl

from cnbr.config import FinancialReconciliationConfig


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sample_indices(length: int, sample_count: int) -> list[int]:
    if length <= sample_count:
        return list(range(length))
    return sorted(
        {round(index * (length - 1) / (sample_count - 1)) for index in range(sample_count)}
    )


def reconcile_financial_values(
    config: FinancialReconciliationConfig, repo_root: Path
) -> dict[str, object]:
    """Verify canonical values against stored occurrence operands without source re-ingestion."""
    values = pl.read_parquet(repo_root / config.values_path)
    facts = pl.read_parquet(repo_root / config.occurrence_path).select("fact_id", "value_raw")
    facts_by_id = {
        str(row["fact_id"]): Decimal(str(row["value_raw"])) for row in facts.iter_rows(named=True)
    }
    audit_rows: list[dict[str, object]] = []
    for value in values.iter_rows(named=True):
        operands = cast(list[str], value["operand_fact_ids"])
        formula = str(value["formula"])
        status = "pass"
        expected: Decimal | None = None
        if formula == "unresolved_missing_prior_cumulative":
            status = "expected_unresolved"
        elif any(operand not in facts_by_id for operand in operands):
            status = "fail_missing_operand"
        elif formula in {"direct_quarter", "direct_instant"} and len(operands) == 1:
            expected = facts_by_id[operands[0]]
        elif formula == "cumulative_minus_prior_cumulative_v1" and len(operands) == 2:
            expected = facts_by_id[operands[0]] - facts_by_id[operands[1]]
        else:
            status = "fail_formula_operands"
        observed_raw = value["value"]
        observed = Decimal(str(observed_raw)) if observed_raw is not None else None
        if expected is not None and observed != expected:
            status = "fail_value_mismatch"
        audit_rows.append(
            {
                "schema_version": config.schema_version,
                "company_id": str(value["company_id"]),
                "ticker": str(value["ticker"]),
                "fiscal_year": int(value["fiscal_year"]),
                "fiscal_quarter": int(value["fiscal_quarter"]),
                "metric": str(value["metric"]),
                "formula": formula,
                "status": status,
                "operand_count": len(operands),
                "canonical_value": str(observed) if observed is not None else None,
                "recomputed_value": str(expected) if expected is not None else None,
            }
        )
    audited = pl.DataFrame(audit_rows).sort(
        "ticker", "formula", "fiscal_year", "fiscal_quarter", "metric"
    )
    failures = audited.filter(pl.col("status").str.starts_with("fail"))
    if not failures.is_empty():
        raise ValueError(f"Financial reconciliation failed for {failures.height} canonical values")
    detail_path = repo_root / config.detail_path
    manifest_path = repo_root / config.manifest_path
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    for _, group in audited.group_by("ticker", "formula", maintain_order=True):
        rows = group.to_dicts()
        samples.extend(
            rows[index] for index in _sample_indices(len(rows), config.samples_per_formula_ticker)
        )
    with detail_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(audited.columns))
        writer.writeheader()
        writer.writerows(samples)
    statuses = {
        str(row["status"]): row["len"]
        for row in audited.group_by("status").len().iter_rows(named=True)
    }
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "audited_value_count": audited.height,
        "sampled_value_count": len(samples),
        "status_counts": statuses,
        "values_sha256": _sha256(repo_root / config.values_path),
        "occurrences_sha256": _sha256(repo_root / config.occurrence_path),
        "detail_sha256": _sha256(detail_path),
        "interpretation": (
            "Local arithmetic/provenance audit passed; it does not replace an independent filing "
            "presentation review."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
