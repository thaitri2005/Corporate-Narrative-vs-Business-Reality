from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast

import polars as pl

from cnbr.config import ConceptFamilyConfig, SecCoverageConfig

ALLOWED_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}
ALLOWED_FISCAL_PERIODS = {"Q1", "Q2", "Q3", "Q4", "FY"}


def _load_object(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_bytes())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(dict[str, Any], payload)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _periods_for_concept(
    fact: dict[str, Any], start_year: int, end_year: int
) -> set[tuple[int, str]]:
    units_raw = fact.get("units")
    if not isinstance(units_raw, dict):
        return set()
    units = cast(dict[str, Any], units_raw)
    usd_facts_raw = units.get("USD")
    if not isinstance(usd_facts_raw, list):
        return set()
    usd_facts = cast(list[Any], usd_facts_raw)
    periods: set[tuple[int, str]] = set()
    for item_raw in usd_facts:
        if not isinstance(item_raw, dict):
            continue
        item = cast(dict[str, Any], item_raw)
        if item.get("form") not in ALLOWED_FORMS:
            continue
        fiscal_year = item.get("fy")
        fiscal_period = item.get("fp")
        if (
            isinstance(fiscal_year, int)
            and start_year <= fiscal_year <= end_year
            and isinstance(fiscal_period, str)
            and fiscal_period in ALLOWED_FISCAL_PERIODS
        ):
            periods.add((fiscal_year, fiscal_period))
    return periods


def _coverage_row(
    *,
    cik: str,
    ticker: str,
    entity_name: str,
    metric: str,
    family: ConceptFamilyConfig,
    us_gaap: dict[str, Any],
    start_year: int,
    end_year: int,
) -> dict[str, object]:
    union: set[tuple[int, str]] = set()
    concepts_present: list[str] = []
    for concept in family.concepts:
        raw_fact_unknown = us_gaap.get(concept)
        if not isinstance(raw_fact_unknown, dict):
            continue
        raw_fact = cast(dict[str, Any], raw_fact_unknown)
        periods = _periods_for_concept(raw_fact, start_year, end_year)
        if periods:
            concepts_present.append(concept)
            union.update(periods)
    years = sorted({year for year, _ in union})
    return {
        "cik": cik,
        "ticker": ticker,
        "entity_name": entity_name,
        "metric": metric,
        "raw_concepts_present": ";".join(concepts_present),
        "raw_concept_count": len(concepts_present),
        "fiscal_period_count": len(union),
        "expected_periods": family.expected_periods,
        "coverage_ratio": round(min(1.0, len(union) / family.expected_periods), 4),
        "first_fiscal_year": years[0] if years else None,
        "last_fiscal_year": years[-1] if years else None,
    }


def build_concept_coverage(config: SecCoverageConfig, repo_root: Path) -> dict[str, object]:
    """Measure candidate GAAP-concept availability without normalizing or deriving values."""
    input_dir = repo_root / config.input_dir
    company_fact_paths = sorted(input_dir.glob("*/companyfacts.json"))
    if not company_fact_paths:
        raise ValueError(f"No Company Facts files found under {input_dir}")

    detail_rows: list[dict[str, object]] = []
    input_hashes: dict[str, str] = {}
    for facts_path in company_fact_paths:
        cik = facts_path.parent.name
        payload = _load_object(facts_path)
        submissions_path = facts_path.with_name("submissions.json")
        submissions = _load_object(submissions_path)
        tickers_raw = submissions.get("tickers")
        tickers = cast(list[Any], tickers_raw) if isinstance(tickers_raw, list) else []
        ticker = str(tickers[0]) if tickers else ""
        entity_name = str(payload.get("entityName", ""))
        facts = payload.get("facts")
        facts_typed = cast(dict[str, Any], facts) if isinstance(facts, dict) else {}
        us_gaap_raw = facts_typed.get("us-gaap")
        us_gaap = cast(dict[str, Any], us_gaap_raw) if isinstance(us_gaap_raw, dict) else {}
        for metric, family in config.concepts.items():
            detail_rows.append(
                _coverage_row(
                    cik=cik,
                    ticker=ticker,
                    entity_name=entity_name,
                    metric=metric,
                    family=family,
                    us_gaap=us_gaap,
                    start_year=config.start_fiscal_year,
                    end_year=config.end_fiscal_year,
                )
            )
        input_hashes[facts_path.relative_to(repo_root).as_posix()] = _sha256(facts_path)

    detail = pl.DataFrame(detail_rows).sort("metric", "ticker")
    detail_path = repo_root / config.detail_path
    summary_path = repo_root / config.summary_path
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    detail.write_csv(detail_path)

    metrics: list[dict[str, object]] = []
    for metric in sorted(config.concepts):
        metric_rows = [row for row in detail_rows if row["metric"] == metric]
        ratios = [cast(float, row["coverage_ratio"]) for row in metric_rows]
        metrics.append(
            {
                "metric": metric,
                "companies_with_coverage": sum(
                    cast(int, row["fiscal_period_count"]) > 0 for row in metric_rows
                ),
                "company_count": len(metric_rows),
                "minimum_coverage_ratio": min(ratios),
                "median_coverage_ratio": median(ratios),
                "maximum_coverage_ratio": max(ratios),
            }
        )
    summary: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "start_fiscal_year": config.start_fiscal_year,
        "end_fiscal_year": config.end_fiscal_year,
        "company_count": len(company_fact_paths),
        "config_sha256": config.content_hash(),
        "input_sha256": input_hashes,
        "metrics": metrics,
        "interpretation": (
            "Availability screen only. Counts do not establish dimensional, duration, fiscal, "
            "restatement, or cross-company semantic comparability."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
