from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast

import polars as pl

from cnbr.config import TranscriptAuditConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _section_metrics(section: object) -> tuple[int, int, int, int]:
    turns = cast(list[dict[str, Any]], section)
    segments = [str(segment) for turn in turns for segment in turn.get("speech", [])]
    return len(turns), len(segments), sum(len(text.split()) for text in segments), sum(
        not text.strip() for text in segments
    )


def build_transcript_audit(
    config: TranscriptAuditConfig, repo_root: Path
) -> dict[str, object]:
    """Profile call coverage and section integrity without exposing transcript text."""
    input_path = repo_root / config.input_path
    calls = pl.read_parquet(input_path)
    rows: list[dict[str, object]] = []
    for row in calls.iter_rows(named=True):
        prepared = _section_metrics(row["prepared_remarks"])
        qa = _section_metrics(row["questions_and_answers"])
        participants = cast(list[object], row["participants"])
        rows.append(
            {
                "ticker": row["ticker"],
                "call_date": row["date"],
                "year": int(str(row["date"])[:4]),
                "participant_count": len(participants),
                "prepared_turn_count": prepared[0],
                "prepared_segment_count": prepared[1],
                "prepared_word_count": prepared[2],
                "prepared_blank_segment_count": prepared[3],
                "qa_turn_count": qa[0],
                "qa_segment_count": qa[1],
                "qa_word_count": qa[2],
                "qa_blank_segment_count": qa[3],
                "total_word_count": prepared[2] + qa[2],
            }
        )
    detail = pl.DataFrame(rows).sort("ticker", "call_date")
    if detail.is_empty():
        raise ValueError("Transcript audit input is empty")
    company = (
        detail.group_by("ticker")
        .agg(
            pl.len().alias("call_count"),
            pl.col("call_date").min().alias("first_call_date"),
            pl.col("call_date").max().alias("last_call_date"),
            pl.col("year").n_unique().alias("covered_year_count"),
            pl.col("total_word_count").median().alias("median_words_per_call"),
            pl.col("prepared_blank_segment_count").sum().alias("prepared_blank_segments"),
            pl.col("qa_blank_segment_count").sum().alias("qa_blank_segments"),
        )
        .with_columns(
            (pl.col("call_count") >= config.minimum_calls).alias("meets_call_threshold"),
            pl.col("last_call_date").str.slice(0, 4).cast(pl.Int32).alias("last_call_year"),
        )
        .sort("ticker")
    )
    call_detail_path = repo_root / config.call_detail_path
    company_summary_path = repo_root / config.company_summary_path
    manifest_path = repo_root / config.manifest_path
    for path in (call_detail_path, company_summary_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.write_csv(call_detail_path)
    company.write_csv(company_summary_path)
    counts = cast(list[int], company["call_count"].to_list())
    word_counts = cast(list[int], detail["total_word_count"].to_list())
    end_year_distribution = {
        str(row["last_call_year"]): row["len"]
        for row in company.group_by("last_call_year").len().sort("last_call_year").iter_rows(
            named=True
        )
    }
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "input_path": config.input_path.as_posix(),
        "input_sha256": _sha256(input_path),
        "call_count": detail.height,
        "company_count": company.height,
        "minimum_calls_required": config.minimum_calls,
        "eligible_company_count": company.filter(pl.col("meets_call_threshold")).height,
        "companies_with_2024_call": company.filter(pl.col("last_call_year") == 2024).height,
        "eligible_companies_with_2024_call": company.filter(
            pl.col("meets_call_threshold") & (pl.col("last_call_year") == 2024)
        ).height,
        "company_end_year_distribution": end_year_distribution,
        "calls_per_company": {
            "minimum": min(counts),
            "median": median(counts),
            "maximum": max(counts),
        },
        "blank_prepared_segment_count": int(detail["prepared_blank_segment_count"].sum()),
        "blank_qa_segment_count": int(detail["qa_blank_segment_count"].sum()),
        "total_word_count": sum(word_counts),
        "median_words_per_call": median(word_counts),
        "call_detail_path": config.call_detail_path.as_posix(),
        "company_summary_path": config.company_summary_path.as_posix(),
        "release_class": "non-text quality metadata; review before public release",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
