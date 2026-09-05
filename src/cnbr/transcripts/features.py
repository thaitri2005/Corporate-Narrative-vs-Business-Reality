from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import polars as pl

from cnbr.config import NarrativeFeatureConfig

BUCKETS = (
    "management_prepared_words",
    "management_qa_words",
    "analyst_prepared_words",
    "analyst_qa_words",
    "operator_words",
    "unknown_words",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_narrative_structure_features(
    config: NarrativeFeatureConfig, repo_root: Path
) -> dict[str, object]:
    """Aggregate role/section structure without semantic modeling or text release."""
    utterances = pl.read_parquet(repo_root / config.utterances_path)
    mappings = pl.read_parquet(repo_root / config.call_mappings_path)
    mapping_by_call = {str(row["call_id"]): row for row in mappings.iter_rows(named=True)}
    aggregate: dict[str, dict[str, object]] = {}
    excluded_flags = set(config.excluded_quality_flags)
    for utterance in utterances.iter_rows(named=True):
        call_id = str(utterance["call_id"])
        mapping = mapping_by_call.get(call_id)
        if mapping is None:
            continue
        record = aggregate.setdefault(
            call_id,
            {
                "schema_version": config.schema_version,
                "call_id": call_id,
                "company_id": str(mapping["company_id"]),
                "ticker": str(mapping["ticker"]),
                "fiscal_year": int(mapping["fiscal_year"]),
                "fiscal_quarter": int(mapping["fiscal_quarter"]),
                "call_date": str(mapping["call_date"]),
                "eligible_word_count": 0,
                "excluded_utterance_count": 0,
                **{bucket: 0 for bucket in BUCKETS},
            },
        )
        flags = set(cast(list[str], utterance["quality_flags"]))
        if flags & excluded_flags:
            record["excluded_utterance_count"] = cast(int, record["excluded_utterance_count"]) + 1
            continue
        words = int(utterance["word_count"])
        record["eligible_word_count"] = cast(int, record["eligible_word_count"]) + words
        role = str(utterance["speaker_role"])
        section = str(utterance["section"])
        if role in {"executive", "company_other"}:
            bucket = (
                "management_prepared_words"
                if section == "prepared_remarks"
                else "management_qa_words"
            )
        elif role == "analyst":
            bucket = (
                "analyst_prepared_words" if section == "prepared_remarks" else "analyst_qa_words"
            )
        elif role == "operator":
            bucket = "operator_words"
        else:
            bucket = "unknown_words"
        record[bucket] = cast(int, record[bucket]) + words
    if len(aggregate) != mappings.height:
        raise ValueError("Not every mapped call produced narrative structure features")
    rows: list[dict[str, object]] = []
    for record in aggregate.values():
        total = cast(int, record["eligible_word_count"])
        if total <= 0:
            raise ValueError(f"Mapped call has no eligible words: {record['call_id']}")
        for bucket in BUCKETS:
            record[bucket.replace("_words", "_share")] = cast(int, record[bucket]) / total
        rows.append(record)
    output = pl.DataFrame(rows).sort("company_id", "fiscal_year", "fiscal_quarter")
    key_columns = ["company_id", "fiscal_year", "fiscal_quarter"]
    if output.select(key_columns).unique().height != output.height:
        raise ValueError("Narrative feature quarter keys are not unique")
    output_path = repo_root / config.output_path
    manifest_path = repo_root / config.manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_parquet(output_path, compression="zstd")
    excluded = cast(list[int], output["excluded_utterance_count"].to_list())
    eligible_words = cast(list[int], output["eligible_word_count"].to_list())
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "observation_count": output.height,
        "company_count": output["company_id"].n_unique(),
        "excluded_utterance_count": sum(excluded),
        "eligible_word_count": sum(eligible_words),
        "utterances_sha256": _sha256(repo_root / config.utterances_path),
        "call_mappings_sha256": _sha256(repo_root / config.call_mappings_path),
        "output_sha256": _sha256(output_path),
        "interpretation": "Structural baselines only; no semantic topic signal or outcome test.",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
