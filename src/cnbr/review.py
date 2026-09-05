from __future__ import annotations

import csv
import html
from pathlib import Path
from typing import Any

import polars as pl

from cnbr.config import FiscalReviewConfig


def _sample_indices(length: int, sample_count: int) -> list[int]:
    if length <= sample_count:
        return list(range(length))
    if sample_count == 1:
        return [length // 2]
    return sorted(
        {round(index * (length - 1) / (sample_count - 1)) for index in range(sample_count)}
    )


def build_fiscal_review_packet(config: FiscalReviewConfig, repo_root: Path) -> dict[str, object]:
    """Create an ignored local HTML packet and metadata-only review checklist."""
    mappings = pl.read_parquet(repo_root / config.mappings_path).sort("ticker", "call_date")
    utterances = pl.read_parquet(repo_root / config.utterances_path)
    selected: list[dict[str, Any]] = []
    for ticker in sorted(mappings["ticker"].unique().to_list()):
        company = mappings.filter(pl.col("ticker") == ticker)
        rows = company.to_dicts()
        selected.extend(
            rows[index] for index in _sample_indices(len(rows), config.samples_per_company)
        )
    prepared_by_call: dict[str, list[str]] = {}
    selected_ids = {str(row["call_id"]) for row in selected}
    for utterance in utterances.iter_rows(named=True):
        call_id = str(utterance["call_id"])
        if call_id in selected_ids and utterance["section"] == "prepared_remarks":
            prepared_by_call.setdefault(call_id, []).append(str(utterance["text"]))

    html_path = repo_root / config.html_path
    checklist_path = repo_root / config.checklist_path
    html_path.parent.mkdir(parents=True, exist_ok=True)
    checklist_path.parent.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    for row in selected:
        call_id = str(row["call_id"])
        excerpt = " ".join(prepared_by_call.get(call_id, []))[: config.excerpt_characters]
        heading = (
            f"{row['ticker']} — call {row['call_date']} — "
            f"FY{row['fiscal_year']} Q{row['fiscal_quarter']}"
        )
        cards.append(
            "<article><h2>"
            + html.escape(heading)
            + "</h2><p>Period end: "
            + html.escape(str(row["period_end"]))
            + " · lag days: "
            + html.escape(str(row["lag_days"]))
            + "</p><pre>"
            + html.escape(excerpt)
            + "</pre></article>"
        )
    document = (
        """<!doctype html><html><head><meta charset="utf-8">
<title>Fiscal mapping review</title>
<style>
body{font-family:system-ui;max-width:1000px;margin:auto;padding:2rem}
article{border-top:1px solid #ccc;padding:1rem 0}
pre{white-space:pre-wrap}
</style>
</head><body><h1>Restricted local fiscal-mapping review</h1>
<p>Do not publish this file. For each call, verify that the excerpt's reported-quarter
language agrees with the assigned fiscal year and quarter, then record the verdict in
the CSV checklist.</p>"""
        + "".join(cards)
        + "</body></html>"
    )
    html_path.write_text(document, encoding="utf-8")
    if not checklist_path.exists():
        with checklist_path.open("w", encoding="utf-8", newline="") as stream:
            fieldnames = [
                "call_id",
                "ticker",
                "call_date",
                "fiscal_year",
                "fiscal_quarter",
                "period_end",
                "lag_days",
                "verdict_pass_fail",
                "reviewer_notes_no_transcript_text",
            ]
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for row in selected:
                writer.writerow({name: row.get(name, "") for name in fieldnames})
    return {
        "sample_count": len(selected),
        "company_count": mappings["ticker"].n_unique(),
        "html_path": config.html_path.as_posix(),
        "checklist_path": config.checklist_path.as_posix(),
        "release_class": "restricted-local-transcript-review",
    }
