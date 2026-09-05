from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import polars as pl

from cnbr.config import FinancialExtractConfig


def _load_json(path: Path) -> dict[str, Any]:
    value: Any = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(dict[str, Any], value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fact_id(cik: str, concept: str, unit: str, source_item_no: int) -> str:
    payload = f"{cik}\x1f{concept}\x1f{unit}\x1f{source_item_no}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _duration_class(start: str | None, end: str) -> tuple[str, int | None]:
    if start is None:
        return "instant", None
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if days <= 120:
        return "quarter", days
    if days <= 200:
        return "half_ytd", days
    if days <= 300:
        return "nine_month_ytd", days
    return "annual", days


def extract_financial_facts(config: FinancialExtractConfig, repo_root: Path) -> dict[str, object]:
    """Extract relevant Company Facts occurrences without selecting canonical values."""
    filing_index = pl.read_parquet(repo_root / config.filing_index_path).filter(
        pl.col("ticker").is_in(config.companies)
    )
    universe = pl.read_parquet(repo_root / config.universe_path).select(
        "ticker", "company_id", "cik"
    )
    identities = {row["ticker"]: row for row in universe.iter_rows(named=True)}
    filings = {str(row["accession_number"]): row for row in filing_index.iter_rows(named=True)}
    concept_to_metric = {
        concept: metric
        for metric, concepts in config.metric_concepts.items()
        for concept in concepts
    }
    rows: list[dict[str, object]] = []
    source_hashes: dict[str, str] = {}
    for ticker in config.companies:
        identity = identities[ticker]
        cik = str(identity["cik"])
        facts_path = repo_root / config.sec_raw_dir / cik / "companyfacts.json"
        payload = _load_json(facts_path)
        source_hashes[facts_path.relative_to(repo_root).as_posix()] = _sha256(facts_path)
        facts_raw = payload.get("facts")
        facts = cast(dict[str, Any], facts_raw) if isinstance(facts_raw, dict) else {}
        gaap_raw = facts.get("us-gaap")
        gaap = cast(dict[str, Any], gaap_raw) if isinstance(gaap_raw, dict) else {}
        for concept, metric in concept_to_metric.items():
            concept_raw = gaap.get(concept)
            concept_data = (
                cast(dict[str, Any], concept_raw) if isinstance(concept_raw, dict) else {}
            )
            units_raw = concept_data.get("units")
            units = cast(dict[str, Any], units_raw) if isinstance(units_raw, dict) else {}
            for unit, items_raw in units.items():
                items = cast(list[Any], items_raw) if isinstance(items_raw, list) else []
                for source_item_no, item_raw in enumerate(items):
                    if not isinstance(item_raw, dict):
                        continue
                    item = cast(dict[str, Any], item_raw)
                    accession = item.get("accn")
                    end = item.get("end")
                    if not isinstance(accession, str) or accession not in filings:
                        continue
                    if not isinstance(end, str):
                        continue
                    filing = filings[accession]
                    start_raw = item.get("start")
                    start = start_raw if isinstance(start_raw, str) else None
                    duration_class, duration_days = _duration_class(start, end)
                    raw_value = item.get("val")
                    rows.append(
                        {
                            "schema_version": config.schema_version,
                            "fact_id": _fact_id(cik, concept, unit, source_item_no),
                            "company_id": str(identity["company_id"]),
                            "cik": cik,
                            "ticker": ticker,
                            "metric": metric,
                            "concept_raw": concept,
                            "unit": unit,
                            "value_raw": json.dumps(raw_value, separators=(",", ":")),
                            "period_start": start,
                            "period_end": end,
                            "duration_class": duration_class,
                            "duration_days": duration_days,
                            "sec_fiscal_year": item.get("fy"),
                            "sec_fiscal_period": item.get("fp"),
                            "sec_frame": item.get("frame"),
                            "accession_number": accession,
                            "form": item.get("form"),
                            "filed_date": item.get("filed"),
                            "accepted_at": filing["accepted_at"],
                            "is_amendment": filing["is_amendment"],
                            "is_current_period": end == filing["report_date"],
                            "source_item_no": source_item_no,
                            "source_file": facts_path.relative_to(repo_root).as_posix(),
                        }
                    )
    if not rows:
        raise ValueError("Financial fact extraction produced no rows")
    output = pl.DataFrame(rows).sort(
        "ticker", "accession_number", "metric", "concept_raw", "source_item_no"
    )
    if output["fact_id"].n_unique() != output.height:
        raise ValueError("Financial fact IDs are not unique")
    output_path = repo_root / config.output_path
    manifest_path = repo_root / config.manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_parquet(output_path, compression="zstd")
    base_accessions = set(
        filing_index.filter(~pl.col("is_amendment"))["accession_number"].to_list()
    )
    metric_coverage = []
    for metric in config.metric_concepts:
        current_accessions = set(
            output.filter(
                (pl.col("metric") == metric)
                & pl.col("is_current_period")
                & ~pl.col("is_amendment")
                & (pl.col("unit") == "USD")
            )["accession_number"].to_list()
        )
        metric_coverage.append(
            {
                "metric": metric,
                "base_filings_with_current_usd_fact": len(current_accessions),
                "base_filing_count": len(base_accessions),
                "complete": current_accessions == base_accessions,
            }
        )
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "fact_occurrence_count": output.height,
        "company_count": len(config.companies),
        "base_filing_count": len(base_accessions),
        "metric_coverage": metric_coverage,
        "source_sha256": source_hashes,
        "output_sha256": _sha256(output_path),
        "interpretation": "Occurrence extraction only; no canonical concept/value selected.",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
