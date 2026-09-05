from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import polars as pl

from cnbr.config import FiscalAlignmentConfig
from cnbr.contracts import CallTimePrecision, FiscalPeriod, validate_fiscal_periods


def _load_json(path: Path) -> dict[str, Any]:
    value: Any = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(dict[str, Any], value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_boundary_candidates(
    company_facts: dict[str, Any], accession: str, report_date: str, concepts: list[str]
) -> list[tuple[date, int, str]]:
    facts_raw = company_facts.get("facts")
    facts = cast(dict[str, Any], facts_raw) if isinstance(facts_raw, dict) else {}
    gaap_raw = facts.get("us-gaap")
    gaap = cast(dict[str, Any], gaap_raw) if isinstance(gaap_raw, dict) else {}
    candidates: list[tuple[date, int, str]] = []
    for concept in concepts:
        concept_raw = gaap.get(concept)
        concept_data = cast(dict[str, Any], concept_raw) if isinstance(concept_raw, dict) else {}
        units_raw = concept_data.get("units")
        units = cast(dict[str, Any], units_raw) if isinstance(units_raw, dict) else {}
        items_raw = units.get("USD")
        items = cast(list[Any], items_raw) if isinstance(items_raw, list) else []
        for item_raw in items:
            if not isinstance(item_raw, dict):
                continue
            item = cast(dict[str, Any], item_raw)
            start = item.get("start")
            fiscal_year = item.get("fy")
            fiscal_period = item.get("fp")
            if (
                item.get("accn") == accession
                and item.get("end") == report_date
                and isinstance(start, str)
                and isinstance(fiscal_year, int)
                and isinstance(fiscal_period, str)
            ):
                candidates.append((date.fromisoformat(start), fiscal_year, fiscal_period))
    return candidates


def _shortest_boundary(
    company_facts: dict[str, Any], accession: str, report_date: str, concepts: list[str]
) -> tuple[date, int, int]:
    end = date.fromisoformat(report_date)
    candidates = _current_boundary_candidates(company_facts, accession, report_date, concepts)
    if not candidates:
        raise ValueError(f"No current-period boundary fact for {accession}")
    shortest_days = min((end - start).days for start, _, _ in candidates)
    shortest = [item for item in candidates if (end - item[0]).days == shortest_days]
    identities = {(fiscal_year, fiscal_period) for _, fiscal_year, fiscal_period in shortest}
    starts = {start for start, _, _ in shortest}
    if len(identities) != 1 or len(starts) != 1:
        raise ValueError(f"Ambiguous current-period boundary facts for {accession}")
    fiscal_year, fiscal_period = identities.pop()
    if fiscal_period in {"FY", "Q4"}:
        quarter = 4
    elif fiscal_period in {"Q1", "Q2", "Q3"}:
        quarter = int(fiscal_period[1])
    else:
        raise ValueError(f"Unsupported SEC fiscal period {fiscal_period} for {accession}")
    return starts.pop(), fiscal_year, quarter


def build_fiscal_alignment(config: FiscalAlignmentConfig, repo_root: Path) -> dict[str, object]:
    """Build a five-company fiscal spine and map date-precision calls without false timestamps."""
    filings = (
        pl.read_parquet(repo_root / config.filing_index_path)
        .filter(~pl.col("is_amendment") & pl.col("ticker").is_in(config.companies))
        .sort("ticker", "report_date")
    )
    calls = pl.read_parquet(repo_root / config.calls_path).filter(
        pl.col("ticker").is_in(config.companies)
    )
    universe = pl.read_parquet(repo_root / config.universe_path).select(
        "ticker", "company_id", "cik"
    )
    identity = {row["ticker"]: row for row in universe.iter_rows(named=True)}
    fact_payloads: dict[str, dict[str, Any]] = {}
    fact_hashes: dict[str, str] = {}
    base_rows: list[dict[str, object]] = []
    previous_by_ticker: dict[str, tuple[int, int, date]] = {}
    for filing in filings.iter_rows(named=True):
        ticker = str(filing["ticker"])
        cik = str(identity[ticker]["cik"])
        facts_path = repo_root / config.sec_raw_dir / cik / "companyfacts.json"
        if cik not in fact_payloads:
            fact_payloads[cik] = _load_json(facts_path)
            fact_hashes[facts_path.relative_to(repo_root).as_posix()] = _sha256(facts_path)
        boundary_start, fiscal_year, fiscal_quarter = _shortest_boundary(
            fact_payloads[cik],
            str(filing["accession_number"]),
            str(filing["report_date"]),
            config.period_boundary_concepts,
        )
        previous = previous_by_ticker.get(ticker)
        period_start = boundary_start
        if previous is not None:
            previous_year, previous_quarter, previous_end = previous
            is_sequential = (
                fiscal_year == previous_year and fiscal_quarter == previous_quarter + 1
            ) or (
                fiscal_year == previous_year + 1 and fiscal_quarter == 1 and previous_quarter == 4
            )
            if not is_sequential:
                raise ValueError(
                    f"Non-sequential fiscal labels for {ticker} at {filing['report_date']}"
                )
            period_start = previous_end + timedelta(days=1)
            if boundary_start > period_start:
                raise ValueError(f"Boundary fact starts after inferred quarter for {ticker}")
        report_date = date.fromisoformat(str(filing["report_date"]))
        previous_by_ticker[ticker] = (fiscal_year, fiscal_quarter, report_date)
        base_rows.append(
            {
                "ticker": ticker,
                "company_id": str(identity[ticker]["company_id"]),
                "cik": cik,
                "fiscal_year": fiscal_year,
                "fiscal_quarter": fiscal_quarter,
                "boundary_fact_start": boundary_start,
                "period_start": period_start,
                "period_end": report_date,
                "filing_accepted_at": datetime.fromisoformat(
                    str(filing["accepted_at"]).replace("Z", "+00:00")
                ),
                "accession_number": str(filing["accession_number"]),
            }
        )

    call_by_period: dict[tuple[str, int, int], dict[str, object]] = {}
    mapping_rows: list[dict[str, object]] = []
    for call in calls.iter_rows(named=True):
        call_date = date.fromisoformat(str(call["call_date"]))
        candidates = [
            row
            for row in base_rows
            if row["ticker"] == call["ticker"]
            and cast(date, row["period_end"]) <= call_date
            and (call_date - cast(date, row["period_end"])).days <= config.maximum_call_lag_days
        ]
        if not candidates:
            raise ValueError(f"No fiscal period in lag window for call {call['call_id']}")
        matched = max(candidates, key=lambda row: cast(date, row["period_end"]))
        key = (
            str(matched["company_id"]),
            cast(int, matched["fiscal_year"]),
            cast(int, matched["fiscal_quarter"]),
        )
        if key in call_by_period:
            raise ValueError(f"Multiple calls map to fiscal period {key}")
        call_by_period[key] = call
        mapping_rows.append(
            {
                "call_id": call["call_id"],
                "company_id": matched["company_id"],
                "ticker": call["ticker"],
                "call_date": call_date,
                "fiscal_year": matched["fiscal_year"],
                "fiscal_quarter": matched["fiscal_quarter"],
                "period_end": matched["period_end"],
                "lag_days": (call_date - cast(date, matched["period_end"])).days,
                "mapping_rule": "latest_preceding_period_end_within_lag_v1",
            }
        )

    periods: list[FiscalPeriod] = []
    for row in base_rows:
        key = (
            str(row["company_id"]),
            cast(int, row["fiscal_year"]),
            cast(int, row["fiscal_quarter"]),
        )
        call = call_by_period.get(key)
        periods.append(
            FiscalPeriod(
                company_id=key[0],
                fiscal_year=key[1],
                fiscal_quarter=key[2],
                period_start=cast(date, row["period_start"]),
                period_end=cast(date, row["period_end"]),
                call_id=str(call["call_id"]) if call else None,
                call_date=date.fromisoformat(str(call["call_date"])) if call else None,
                call_time_precision=CallTimePrecision.DATE if call else None,
                filing_accepted_at=cast(datetime, row["filing_accepted_at"]),
                mapping_source="sec_current_accession_boundary_and_strux_date_v1",
            )
        )
    validate_fiscal_periods(periods)
    period_frame = pl.DataFrame([period.model_dump(mode="json") for period in periods]).sort(
        "company_id", "fiscal_year", "fiscal_quarter"
    )
    mapping_frame = pl.DataFrame(mapping_rows).sort("ticker", "call_date")
    fiscal_path = repo_root / config.fiscal_periods_path
    mappings_path = repo_root / config.call_mappings_path
    manifest_path = repo_root / config.manifest_path
    for path in (fiscal_path, mappings_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    period_frame.write_parquet(fiscal_path, compression="zstd")
    mapping_frame.write_parquet(mappings_path, compression="zstd")
    company_counts = period_frame.group_by("company_id").len()
    periods_per_company = cast(list[int], company_counts["len"].to_list())
    call_lags = cast(list[int], mapping_frame["lag_days"].to_list())
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "company_count": company_counts.height,
        "fiscal_period_count": period_frame.height,
        "minimum_periods_per_company": min(periods_per_company),
        "maximum_periods_per_company": max(periods_per_company),
        "mapped_call_count": mapping_frame.height,
        "unmapped_call_count": calls.height - mapping_frame.height,
        "minimum_call_lag_days": min(call_lags),
        "maximum_call_lag_days": max(call_lags),
        "input_companyfacts_sha256": fact_hashes,
        "fiscal_periods_sha256": _sha256(fiscal_path),
        "call_mappings_sha256": _sha256(mappings_path),
        "interpretation": (
            "Accession-bound thin slice; manual fiscal-label review remains required."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
