from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import polars as pl

from cnbr.config import SecFilingIndexConfig

TARGET_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}
REQUIRED_COLUMNS = (
    "accessionNumber",
    "filingDate",
    "reportDate",
    "acceptanceDateTime",
    "form",
    "primaryDocument",
)


def _load_object(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_bytes())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(dict[str, Any], payload)


def _rows_from_columnar(source: dict[str, Any], source_file: str) -> list[dict[str, str]]:
    columns: dict[str, list[Any]] = {}
    for name in REQUIRED_COLUMNS:
        values = source.get(name)
        if not isinstance(values, list):
            raise ValueError(f"Missing filing column {name!r} in {source_file}")
        columns[name] = cast(list[Any], values)
    lengths = {len(values) for values in columns.values()}
    if len(lengths) != 1:
        raise ValueError(f"Filing columns have unequal lengths in {source_file}")
    count = lengths.pop()
    return [
        {name: str(columns[name][index] or "") for name in REQUIRED_COLUMNS}
        | {"source_file": source_file}
        for index in range(count)
    ]


def build_filing_index(config: SecFilingIndexConfig, repo_root: Path) -> dict[str, object]:
    """Build a deduplicated 10-K/10-Q filing spine from recent and history submissions."""
    input_dir = repo_root / config.input_dir
    rows_by_accession: dict[str, dict[str, object]] = {}
    input_hashes: dict[str, str] = {}
    for company_dir in sorted(path for path in input_dir.iterdir() if path.is_dir()):
        main_path = company_dir / "submissions.json"
        main = _load_object(main_path)
        filings = main.get("filings")
        if not isinstance(filings, dict):
            raise ValueError(f"Missing filings object in {main_path}")
        recent = cast(dict[str, Any], filings).get("recent")
        if not isinstance(recent, dict):
            raise ValueError(f"Missing filings.recent object in {main_path}")
        sources: list[tuple[Path, dict[str, Any]]] = [(main_path, cast(dict[str, Any], recent))]
        history_dir = company_dir / "submissions-history"
        for history_path in sorted(history_dir.glob("*.json")):
            sources.append((history_path, _load_object(history_path)))

        tickers = main.get("tickers")
        ticker_values = cast(list[Any], tickers) if isinstance(tickers, list) else []
        ticker = str(ticker_values[0]) if ticker_values else ""
        entity_name = str(main.get("name", ""))
        fiscal_year_end = str(main.get("fiscalYearEnd", ""))
        cik = company_dir.name
        for source_path, source in sources:
            relative_source = source_path.relative_to(repo_root).as_posix()
            input_hashes[relative_source] = hashlib.sha256(source_path.read_bytes()).hexdigest()
            for raw in _rows_from_columnar(source, relative_source):
                form = raw["form"]
                report_date = raw["reportDate"]
                if form not in TARGET_FORMS or not report_date:
                    continue
                if (
                    not config.study_start.isoformat()
                    <= report_date
                    <= config.study_end.isoformat()
                ):
                    continue
                accession = raw["accessionNumber"]
                normalized: dict[str, object] = {
                    "cik": cik,
                    "ticker": ticker,
                    "entity_name": entity_name,
                    "fiscal_year_end_mmdd": fiscal_year_end,
                    "accession_number": accession,
                    "form": form,
                    "base_form": form.removesuffix("/A"),
                    "is_amendment": form.endswith("/A"),
                    "report_date": report_date,
                    "filing_date": raw["filingDate"],
                    "accepted_at": raw["acceptanceDateTime"],
                    "primary_document": raw["primaryDocument"],
                    "source_file": relative_source,
                }
                prior = rows_by_accession.get(accession)
                comparable = {
                    key: value for key, value in normalized.items() if key != "source_file"
                }
                if prior is not None:
                    prior_comparable = {
                        key: value for key, value in prior.items() if key != "source_file"
                    }
                    if prior_comparable != comparable:
                        raise ValueError(f"Conflicting duplicate accession {accession}")
                    continue
                rows_by_accession[accession] = normalized

    if not rows_by_accession:
        raise ValueError("No target SEC filings found in the configured study window")
    frame = pl.DataFrame(list(rows_by_accession.values())).sort("cik", "report_date", "accepted_at")
    output_path = repo_root / config.output_path
    summary_path = repo_root / config.summary_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(output_path)
    per_company = (
        frame.group_by("ticker")
        .agg(
            pl.len().alias("filing_count"),
            pl.col("report_date").min().alias("first_report_date"),
            pl.col("report_date").max().alias("last_report_date"),
            pl.col("is_amendment").sum().alias("amendment_count"),
        )
        .sort("ticker")
        .to_dicts()
    )
    summary: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "study_start": config.study_start.isoformat(),
        "study_end": config.study_end.isoformat(),
        "company_count": frame["cik"].n_unique(),
        "filing_count": frame.height,
        "amendment_count": int(frame["is_amendment"].sum()),
        "config_sha256": config.content_hash(),
        "input_sha256": input_hashes,
        "companies": per_company,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
