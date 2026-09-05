# ruff: noqa: E501

from __future__ import annotations

import hashlib
import html
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


def _build_review_html(tasks: list[dict[str, object]]) -> str:
    cards: list[str] = []
    for task in tasks:
        data = cast(dict[str, object], task["data"])
        task_id = str(data["task_id"])
        cards.append(
            '<article data-task-id="'
            + html.escape(task_id)
            + '"><h2>'
            + html.escape(str(data["candidate_topic"]))
            + "</h2><p>"
            + html.escape(
                f"{data['ticker']} · FY{data['fiscal_year']} Q{data['fiscal_quarter']} · {data['view']}"
            )
            + "</p><blockquote>"
            + html.escape(str(data["text"]))
            + '</blockquote><label><input type="radio" name="'
            + html.escape(task_id)
            + '" value="yes"> Yes</label><label><input type="radio" name="'
            + html.escape(task_id)
            + '" value="no"> No</label><label><input type="radio" name="'
            + html.escape(task_id)
            + '" value="unsure"> Unsure</label><br><textarea placeholder="Optional brief note; do not copy transcript text"></textarea></article>'
        )
    task_data = json.dumps(
        [
            {
                "task_id": cast(dict[str, object], task["data"])["task_id"],
                "candidate_topic": cast(dict[str, object], task["data"])["candidate_topic"],
            }
            for task in tasks
        ]
    )
    return (
        """<!doctype html><html><head><meta charset="utf-8"><title>Annotation pilot</title>
<style>body{font-family:system-ui;max-width:900px;margin:auto;padding:2rem}article{border-top:1px solid #ccc;padding:1rem 0}blockquote{white-space:pre-wrap;background:#f6f6f6;padding:1rem}label{margin-right:1rem}textarea{width:100%;height:4rem;margin-top:1rem}</style>
</head><body><h1>Restricted local annotation pilot</h1><p>For each excerpt: does it genuinely discuss the candidate topic? Pick Yes, No, or Unsure. Candidate topics are suggestions, not answers. Export your labels when finished; do not publish this page or copy text into notes.</p><button id="export">Download labels</button>"""
        + "".join(cards)
        + """<script>
const tasks = """
        + task_data
        + """;
document.querySelector('#export').onclick=()=>{const labels=tasks.map(task=>{const card=document.querySelector(`[data-task-id="${task.task_id}"]`);const picked=card.querySelector('input:checked');return {...task,verdict:picked?.value||'',notes:card.querySelector('textarea').value};});const blob=new Blob([JSON.stringify(labels,null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='annotation_pilot_labels.json';link.click();URL.revokeObjectURL(link.href);};
</script></body></html>"""
    )


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
            is_match = bool(pattern.search(str(utterance["text"])))
            if (config.selection_mode == "lexical_match" and is_match) or (
                config.selection_mode == "lexical_nonmatch" and not is_match
            ):
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
                        "selection_mode": config.selection_mode,
                        **row,
                    }
                }
            )
    task_ids = [str(cast(dict[str, object], task["data"])["task_id"]) for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Annotation pilot task IDs are not unique")
    tasks_path = repo_root / config.tasks_path
    html_path = repo_root / config.html_path
    manifest_path = repo_root / config.manifest_path
    for path in (tasks_path, html_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(_build_review_html(tasks), encoding="utf-8")
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "taxonomy_version": lexical_config.taxonomy_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "task_count": len(tasks),
        "selected_by_candidate_topic": selected_by_topic,
        "selection_mode": config.selection_mode,
        "utterances_sha256": _sha256(repo_root / config.utterances_path),
        "call_mappings_sha256": _sha256(repo_root / config.call_mappings_path),
        "tasks_sha256": _sha256(tasks_path),
        "html_sha256": _sha256(html_path),
        "release_class": "restricted-local-annotation-tasks",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
