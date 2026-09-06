from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cnbr.config import AnnotationReviewConfig

_VERDICTS = {"yes", "no", "unsure"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_tasks(path: Path) -> dict[str, dict[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Task file must contain a list: {path}")
    tasks: dict[str, dict[str, str]] = {}
    for item in raw:
        data = cast(dict[str, Any], item.get("data", {}))
        task_id = str(data.get("task_id", ""))
        topic = str(data.get("candidate_topic", ""))
        mode = str(data.get("selection_mode", ""))
        if not task_id or not topic or mode not in {"lexical_match", "lexical_nonmatch"}:
            raise ValueError(f"Task file has invalid review metadata: {path}")
        if task_id in tasks:
            raise ValueError(f"Task file has duplicate task_id: {path}")
        tasks[task_id] = {"candidate_topic": topic, "selection_mode": mode}
    return tasks


def _load_labels(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Label file must contain a list: {path}")
    labels: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"Label file has invalid item: {path}")
        task_id = str(item.get("task_id", ""))
        verdict = str(item.get("verdict", "")).strip().lower()
        if not task_id or verdict not in _VERDICTS:
            raise ValueError(f"Label file has missing or invalid verdict: {path}")
        if task_id in labels:
            raise ValueError(f"Label file has duplicate task_id: {path}")
        labels[task_id] = verdict
    return labels


def review_annotation_exports(config: AnnotationReviewConfig, repo_root: Path) -> dict[str, object]:
    """Validate paired local review files and write a transcript-free aggregate manifest."""
    by_topic_mode: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    all_task_ids: set[str] = set()
    task_hashes: list[str] = []
    label_hashes: list[str] = []
    for task_rel, label_rel in zip(config.task_paths, config.label_paths, strict=True):
        task_path = repo_root / task_rel
        label_path = repo_root / label_rel
        tasks = _load_tasks(task_path)
        labels = _load_labels(label_path)
        if set(tasks) != set(labels):
            raise ValueError(f"Task/label IDs differ for pair: {task_rel} / {label_rel}")
        if all_task_ids & set(tasks):
            raise ValueError("Annotation review packets must not reuse task IDs")
        all_task_ids.update(tasks)
        for task_id, task in tasks.items():
            by_topic_mode[(task["candidate_topic"], task["selection_mode"])][labels[task_id]] += 1
        task_hashes.append(_sha256(task_path))
        label_hashes.append(_sha256(label_path))

    strata: list[dict[str, object]] = []
    total_counts: Counter[str] = Counter()
    for (topic, mode), counts in sorted(by_topic_mode.items()):
        total = sum(counts.values())
        comparable = counts["yes"] + counts["no"]
        total_counts.update(counts)
        strata.append(
            {
                "candidate_topic": topic,
                "selection_mode": mode,
                "task_count": total,
                "verdict_counts": {verdict: counts[verdict] for verdict in sorted(_VERDICTS)},
                "comparable_count": comparable,
                "yes_rate_excluding_unsure": (counts["yes"] / comparable) if comparable else None,
                "unsure_rate": counts["unsure"] / total if total else None,
            }
        )
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "packet_count": len(config.task_paths),
        "task_count": len(all_task_ids),
        "verdict_counts": {verdict: total_counts[verdict] for verdict in sorted(_VERDICTS)},
        "strata": strata,
        "task_sha256": task_hashes,
        "label_sha256": label_hashes,
        "release_class": "aggregate-only-annotation-review",
    }
    manifest_path = repo_root / config.manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
