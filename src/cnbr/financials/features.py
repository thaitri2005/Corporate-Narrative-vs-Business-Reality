from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import polars as pl

from cnbr.config import FinancialFeatureConfig


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _feature_id(company_id: str, year: int, quarter: int, metric: str) -> str:
    value = f"{company_id}\x1f{year}\x1f{quarter}\x1f{metric}\x1ffinancial-features-v1"
    return hashlib.sha256(value.encode()).hexdigest()


def _row(
    *,
    company_id: str,
    ticker: str,
    year: int,
    quarter: int,
    period_end: str,
    metric: str,
    value: Decimal,
    unit: str,
    formula: str,
    operands: list[str],
    schema_version: str,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "feature_id": _feature_id(company_id, year, quarter, metric),
        "company_id": company_id,
        "ticker": ticker,
        "fiscal_year": year,
        "fiscal_quarter": quarter,
        "period_end": period_end,
        "metric": metric,
        "value": str(value),
        "unit": unit,
        "formula": formula,
        "operand_keys": operands,
    }


def build_financial_features(config: FinancialFeatureConfig, repo_root: Path) -> dict[str, object]:
    """Derive transparent financial ratios and same-quarter year-over-year growth."""
    values = pl.read_parquet(repo_root / config.input_path)
    by_period: dict[tuple[str, int, int], dict[str, Any]] = {}
    for value_row in values.iter_rows(named=True):
        key = (
            str(value_row["company_id"]),
            int(value_row["fiscal_year"]),
            int(value_row["fiscal_quarter"]),
        )
        period = by_period.setdefault(
            key,
            {
                "ticker": str(value_row["ticker"]),
                "period_end": str(value_row["period_end"]),
                "metrics": {},
            },
        )
        metrics = period["metrics"]
        if not isinstance(metrics, dict):
            raise ValueError("Invalid financial period metric container")
        cast(dict[str, object], metrics)[str(value_row["metric"])] = value_row["value"]

    rows: list[dict[str, object]] = []
    for (company_id, year, quarter), period in sorted(by_period.items()):
        metrics = period["metrics"]
        if not isinstance(metrics, dict):
            raise ValueError("Invalid financial period metric container")
        metrics_dict = cast(dict[str, object], metrics)
        typed_metrics: dict[str, Decimal | None] = {
            name: Decimal(str(raw)) if raw is not None else None
            for name, raw in metrics_dict.items()
        }
        ticker = str(period["ticker"])
        period_end = str(period["period_end"])
        for metric, value in typed_metrics.items():
            if value is not None:
                rows.append(
                    _row(
                        company_id=company_id,
                        ticker=ticker,
                        year=year,
                        quarter=quarter,
                        period_end=period_end,
                        metric=metric,
                        value=value,
                        unit="USD",
                        formula="canonical_quarter_value_v1",
                        operands=[f"{company_id}:{year}:Q{quarter}:{metric}"],
                        schema_version=config.schema_version,
                    )
                )
        revenue = typed_metrics.get("revenue")
        for numerator_name, feature_name in (
            ("operating_income", "operating_margin"),
            ("capital_expenditure", "capital_expenditure_to_revenue"),
        ):
            numerator = typed_metrics.get(numerator_name)
            if revenue is not None and revenue != 0 and numerator is not None:
                rows.append(
                    _row(
                        company_id=company_id,
                        ticker=ticker,
                        year=year,
                        quarter=quarter,
                        period_end=period_end,
                        metric=feature_name,
                        value=numerator / revenue,
                        unit="ratio",
                        formula=f"{numerator_name}_divided_by_revenue_v1",
                        operands=[
                            f"{company_id}:{year}:Q{quarter}:{numerator_name}",
                            f"{company_id}:{year}:Q{quarter}:revenue",
                        ],
                        schema_version=config.schema_version,
                    )
                )
        previous = by_period.get((company_id, year - 1, quarter))
        if previous is None:
            continue
        previous_metrics_raw = previous["metrics"]
        if not isinstance(previous_metrics_raw, dict):
            raise ValueError("Invalid prior financial period metric container")
        previous_metrics = cast(dict[str, object], previous_metrics_raw)
        for source_metric, feature_name in (
            ("revenue", "revenue_yoy"),
            ("inventory", "inventory_yoy"),
        ):
            current_value = typed_metrics.get(source_metric)
            previous_raw = previous_metrics.get(source_metric)
            previous_value = Decimal(str(previous_raw)) if previous_raw is not None else None
            if current_value is None or previous_value is None or previous_value == 0:
                continue
            rows.append(
                _row(
                    company_id=company_id,
                    ticker=ticker,
                    year=year,
                    quarter=quarter,
                    period_end=period_end,
                    metric=feature_name,
                    value=current_value / previous_value - Decimal(1),
                    unit="ratio",
                    formula=f"{source_metric}_same_quarter_yoy_v1",
                    operands=[
                        f"{company_id}:{year}:Q{quarter}:{source_metric}",
                        f"{company_id}:{year - 1}:Q{quarter}:{source_metric}",
                    ],
                    schema_version=config.schema_version,
                )
            )
    output = pl.DataFrame(rows).sort("company_id", "fiscal_year", "fiscal_quarter", "metric")
    if output["feature_id"].n_unique() != output.height:
        raise ValueError("Financial feature IDs are not unique")
    output_path = repo_root / config.output_path
    manifest_path = repo_root / config.manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_parquet(output_path, compression="zstd")
    metric_counts = {
        str(row["metric"]): row["len"]
        for row in output.group_by("metric").len().sort("metric").iter_rows(named=True)
    }
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "feature_count": output.height,
        "company_count": output["company_id"].n_unique(),
        "metric_counts": metric_counts,
        "input_sha256": _sha256(repo_root / config.input_path),
        "output_sha256": _sha256(output_path),
        "interpretation": "Mechanical features only; no outcome association has been analyzed.",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
