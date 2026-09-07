# ruff: noqa: E501

from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cnbr.config import AnnotationAdjudicationConfig
from cnbr.transcripts.annotation_review import _load_labels


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_task_data(path: Path) -> dict[str, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Task file must contain a list: {path}")
    records: dict[str, dict[str, Any]] = {}
    for item in raw:
        data = cast(dict[str, Any], item.get("data", {}))
        task_id = str(data.get("task_id", ""))
        if not task_id or not isinstance(data.get("text"), str):
            raise ValueError(f"Task file has invalid adjudication data: {path}")
        if task_id in records:
            raise ValueError(f"Task file has duplicate task_id: {path}")
        records[task_id] = data
    return records


def _render_html(tasks: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for task in tasks:
        task_id = html.escape(str(task["task_id"]))
        cards.append(
            f'<article data-task-id="{task_id}"><h2>{html.escape(str(task["candidate_topic"]))}</h2>'
            f"<p>Reviewer A: {html.escape(str(task['reviewer_a_verdict']))}; "
            f"Reviewer B: {html.escape(str(task['reviewer_b_verdict']))}</p>"
            f"<blockquote>{html.escape(str(task['text']))}</blockquote>"
            f'<label><input type="radio" name="{task_id}" value="yes"> Yes</label>'
            f'<label><input type="radio" name="{task_id}" value="no"> No</label>'
            f'<label><input type="radio" name="{task_id}" value="unsure"> Unsure</label></article>'
        )
    metadata = json.dumps(
        [{"task_id": task["task_id"], "candidate_topic": task["candidate_topic"]} for task in tasks]
    )
    return (
        """<!doctype html><html><head><meta charset="utf-8"><title>Restricted local adjudication</title>
<style>body{font-family:system-ui;max-width:900px;margin:auto;padding:2rem}article{border-top:1px solid #ccc;padding:1rem 0}blockquote{white-space:pre-wrap;background:#f6f6f6;padding:1rem}label{margin-right:1rem}</style>
</head><body><h1>Restricted local adjudication</h1><p>Resolve each disagreement using the codebook. Do not publish or copy transcript text.</p><button id="export">Download adjudications</button>"""
        + "".join(cards)
        + """<script>
const tasks = """
        + metadata
        + """;
document.querySelector('#export').onclick=()=>{const rows=tasks.map(task=>{const picked=document.querySelector(`[data-task-id="${task.task_id}"] input:checked`);return {...task,verdict:picked?.value||''};});const blob=new Blob([JSON.stringify(rows,null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='annotation_adjudications.json';link.click();URL.revokeObjectURL(link.href);};
</script></body></html>"""
    )


def build_annotation_adjudication(
    config: AnnotationAdjudicationConfig, repo_root: Path
) -> dict[str, object]:
    """Create a local-only adjudication packet for disagreements; manifest never contains text."""
    tasks: list[dict[str, Any]] = []
    strata: Counter[str] = Counter()
    hashes: dict[str, list[str]] = {"task": [], "reviewer_a": [], "reviewer_b": []}
    seen_ids: set[str] = set()
    for task_rel, a_rel, b_rel in zip(
        config.task_paths, config.reviewer_a_label_paths, config.reviewer_b_label_paths, strict=True
    ):
        task_file, a_file, b_file = repo_root / task_rel, repo_root / a_rel, repo_root / b_rel
        records, reviewer_a, reviewer_b = (
            _load_task_data(task_file),
            _load_labels(a_file),
            _load_labels(b_file),
        )
        if set(records) != set(reviewer_a) or set(records) != set(reviewer_b):
            raise ValueError(f"Task/label IDs differ for adjudication pair: {task_rel}")
        if seen_ids & set(records):
            raise ValueError("Adjudication packets must not reuse task IDs")
        seen_ids.update(records)
        for task_id, data in records.items():
            if reviewer_a[task_id] != reviewer_b[task_id]:
                tasks.append(
                    {
                        **data,
                        "reviewer_a_verdict": reviewer_a[task_id],
                        "reviewer_b_verdict": reviewer_b[task_id],
                    }
                )
                strata[f"{data['candidate_topic']}|{data['selection_mode']}"] += 1
        hashes["task"].append(_sha256(task_file))
        hashes["reviewer_a"].append(_sha256(a_file))
        hashes["reviewer_b"].append(_sha256(b_file))
    tasks_path, html_path, manifest_path = (
        repo_root / config.tasks_path,
        repo_root / config.html_path,
        repo_root / config.manifest_path,
    )
    for path in (tasks_path, html_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(
        json.dumps([{"data": task} for task in tasks], indent=2) + "\n", encoding="utf-8"
    )
    html_path.write_text(_render_html(tasks), encoding="utf-8")
    manifest = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "task_count": len(tasks),
        "disagreements_by_stratum": dict(sorted(strata.items())),
        "input_sha256": hashes,
        "tasks_sha256": _sha256(tasks_path),
        "html_sha256": _sha256(html_path),
        "release_class": "restricted-local-annotation-adjudication",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
