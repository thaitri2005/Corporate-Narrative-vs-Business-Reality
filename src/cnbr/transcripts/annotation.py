from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import polars as pl

from cnbr.config import AnnotationPilotConfig, load_lexical_baseline_config
from cnbr.transcripts.lexical import view_for


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _task_id(topic_id: str, call_id: str, turn_index: int) -> str:
    return hashlib.sha256(f"{topic_id}|{call_id}|{turn_index}".encode()).hexdigest()


def build_annotation_pilot(config: AnnotationPilotConfig, repo_root: Path) -> dict[str, object]:
    """Create restricted local tasks; metadata never includes transcript excerpts."""
    lexical_config = load_lexical_baseline_config(repo_root / config.lexical_config_path)
    utterances = pl.read_parquet(repo_root / config.utterances_path)
    mappings = pl.read_parquet(repo_root / config.call_mappings_path)
    mapping_by_call = {str(row["call_id"]): row for row in mappings.iter_rows(named=True)}
    patterns = [
        (topic.topic_id, re.compile("(?:" + "|".join(topic.patterns) + ")", re.I))
        for topic in lexical_config.topics
    ]
    excluded_flags = set(config.excluded_quality_flags)
    candidates: dict[str, list[dict[str, Any]]] = {topic_id: [] for topic_id, _ in patterns}
    for utterance in utterances.iter_rows(named=True):
        call_id = str(utterance["call_id"])
        mapping = mapping_by_call.get(call_id)
        if mapping is None or set(cast(list[str], utterance["quality_flags"])) & excluded_flags:
            continue
        view = view_for(str(utterance["speaker_role"]), str(utterance["section"]))
        if view is None:
            continue
        for topic_id, pattern in patterns:
            if pattern.search(str(utterance["text"])):
                candidates[topic_id].append(
                    {
                        "call_id": call_id,
                        "turn_index": int(utterance["sequence_no"]),
                        "ticker": str(mapping["ticker"]),
                        "fiscal_year": int(mapping["fiscal_year"]),
                        "fiscal_quarter": int(mapping["fiscal_quarter"]),
                        "view": view,
                        "text": str(utterance["text"]),
                    }
                )
    tasks: list[dict[str, object]] = []
    selected_by_topic: dict[str, int] = {}
    for topic_id, rows in candidates.items():
        selected = sorted(
            rows,
            key=lambda row: _task_id(topic_id, str(row["call_id"]), int(row["turn_index"])),
        )[: config.samples_per_topic]
        selected_by_topic[topic_id] = len(selected)
        for row in selected:
            tasks.append(
                {
                    "data": {
                        "task_id": _task_id(topic_id, str(row["call_id"]), int(row["turn_index"])),
                        "candidate_topic": topic_id,
                        **row,
                    }
                }
            )
    task_ids = [str(cast(dict[str, object], task["data"])["task_id"]) for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Annotation pilot task IDs are not unique")
    tasks_path = repo_root / config.tasks_path
    manifest_path = repo_root / config.manifest_path
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "taxonomy_version": lexical_config.taxonomy_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "task_count": len(tasks),
        "selected_by_candidate_topic": selected_by_topic,
        "utterances_sha256": _sha256(repo_root / config.utterances_path),
        "call_mappings_sha256": _sha256(repo_root / config.call_mappings_path),
        "tasks_sha256": _sha256(tasks_path),
        "release_class": "restricted-local-annotation-tasks",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
