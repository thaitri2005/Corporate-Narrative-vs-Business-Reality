from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import polars as pl

from cnbr.config import LexicalBaselineConfig


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _view_for(role: str, section: str) -> str | None:
    if role in {"executive", "company_other"}:
        return "management_prepared" if section == "prepared_remarks" else "management_qa"
    if role == "analyst":
        return "analyst_prepared" if section == "prepared_remarks" else "analyst_qa"
    return None


def build_lexical_baseline(config: LexicalBaselineConfig, repo_root: Path) -> dict[str, object]:
    """Build local dictionary-discovery features without exporting transcript text."""
    utterances = pl.read_parquet(repo_root / config.utterances_path)
    mappings = pl.read_parquet(repo_root / config.call_mappings_path)
    mapping_by_call = {str(row["call_id"]): row for row in mappings.iter_rows(named=True)}
    topics = [
        (topic.topic_id, re.compile("(?:" + "|".join(topic.patterns) + ")", re.I))
        for topic in config.topics
    ]
    eligible_views = set(config.views)
    excluded_flags = set(config.excluded_quality_flags)
    aggregates: dict[tuple[str, str, str], dict[str, Any]] = {}
    for mapping in mappings.iter_rows(named=True):
        call_id = str(mapping["call_id"])
        for view in eligible_views:
            for topic_id, _ in topics:
                aggregates[(call_id, view, topic_id)] = {
                    "schema_version": config.schema_version,
                    "taxonomy_version": config.taxonomy_version,
                    "call_id": call_id,
                    "company_id": str(mapping["company_id"]),
                    "ticker": str(mapping["ticker"]),
                    "fiscal_year": int(mapping["fiscal_year"]),
                    "fiscal_quarter": int(mapping["fiscal_quarter"]),
                    "view": view,
                    "topic_id": topic_id,
                    "eligible_word_count": 0,
                    "matched_utterance_count": 0,
                    "matched_word_count": 0,
                }
    for utterance in utterances.iter_rows(named=True):
        call_id = str(utterance["call_id"])
        mapping = mapping_by_call.get(call_id)
        if mapping is None or set(cast(list[str], utterance["quality_flags"])) & excluded_flags:
            continue
        view = _view_for(str(utterance["speaker_role"]), str(utterance["section"]))
        if view not in eligible_views:
            continue
        words = int(utterance["word_count"])
        text = str(utterance["text"])
        for topic_id, pattern in topics:
            key = (call_id, view, topic_id)
            record = aggregates[key]
            record["eligible_word_count"] = cast(int, record["eligible_word_count"]) + words
            if pattern.search(text):
                record["matched_utterance_count"] = cast(int, record["matched_utterance_count"]) + 1
                record["matched_word_count"] = cast(int, record["matched_word_count"]) + words
    expected_rows = mappings.height * len(eligible_views) * len(topics)
    if len(aggregates) != expected_rows:
        raise ValueError("Not every mapped call/view/topic combination produced a lexical feature")
    rows: list[dict[str, object]] = []
    for record in aggregates.values():
        eligible_words = cast(int, record["eligible_word_count"])
        record["matched_word_share"] = (
            cast(int, record["matched_word_count"]) / eligible_words if eligible_words else None
        )
        rows.append(record)
    output = pl.DataFrame(rows).sort(
        "company_id", "fiscal_year", "fiscal_quarter", "view", "topic_id"
    )
    key_columns = ["call_id", "view", "topic_id"]
    if output.select(key_columns).unique().height != output.height:
        raise ValueError("Lexical feature keys are not unique")
    output_path = repo_root / config.output_path
    manifest_path = repo_root / config.manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_parquet(output_path, compression="zstd")
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "taxonomy_version": config.taxonomy_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "observation_count": output.height,
        "call_count": output["call_id"].n_unique(),
        "topic_count": len(topics),
        "views": sorted(eligible_views),
        "utterances_sha256": _sha256(repo_root / config.utterances_path),
        "call_mappings_sha256": _sha256(repo_root / config.call_mappings_path),
        "output_sha256": _sha256(output_path),
        "interpretation": (
            "Local lexical discovery baseline only; patterns are not validated labels and must not "
            "be used for confirmatory analysis."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
