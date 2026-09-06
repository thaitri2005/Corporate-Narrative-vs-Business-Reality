from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cnbr.config import AnnotationAgreementConfig, AnnotationReviewConfig

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


def _cohen_kappa(reviewer_a: list[str], reviewer_b: list[str]) -> float | None:
    if not reviewer_a:
        return None
    observed = sum(a == b for a, b in zip(reviewer_a, reviewer_b, strict=True)) / len(reviewer_a)
    a_counts = Counter(reviewer_a)
    b_counts = Counter(reviewer_b)
    expected = sum(
        (a_counts[verdict] / len(reviewer_a)) * (b_counts[verdict] / len(reviewer_a))
        for verdict in _VERDICTS
    )
    return None if expected == 1 else (observed - expected) / (1 - expected)


def measure_annotation_agreement(
    config: AnnotationAgreementConfig, repo_root: Path
) -> dict[str, object]:
    """Measure two complete local reviews using aggregate-only agreement statistics."""
    by_topic_mode: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    all_pairs: list[tuple[str, str]] = []
    hashes: dict[str, list[str]] = {"task": [], "reviewer_a": [], "reviewer_b": []}
    seen_task_ids: set[str] = set()
    for task_rel, a_rel, b_rel in zip(
        config.task_paths, config.reviewer_a_label_paths, config.reviewer_b_label_paths, strict=True
    ):
        task_path, a_path, b_path = repo_root / task_rel, repo_root / a_rel, repo_root / b_rel
        tasks, reviewer_a, reviewer_b = (
            _load_tasks(task_path),
            _load_labels(a_path),
            _load_labels(b_path),
        )
        if set(tasks) != set(reviewer_a) or set(tasks) != set(reviewer_b):
            raise ValueError(f"Task/label IDs differ for agreement pair: {task_rel}")
        if seen_task_ids & set(tasks):
            raise ValueError("Annotation agreement packets must not reuse task IDs")
        seen_task_ids.update(tasks)
        for task_id, task in tasks.items():
            pair = (reviewer_a[task_id], reviewer_b[task_id])
            by_topic_mode[(task["candidate_topic"], task["selection_mode"])].append(pair)
            all_pairs.append(pair)
        hashes["task"].append(_sha256(task_path))
        hashes["reviewer_a"].append(_sha256(a_path))
        hashes["reviewer_b"].append(_sha256(b_path))

    def metrics(pairs: list[tuple[str, str]]) -> dict[str, object]:
        a, b = [pair[0] for pair in pairs], [pair[1] for pair in pairs]
        return {
            "task_count": len(pairs),
            "exact_agreement": sum(left == right for left, right in pairs) / len(pairs)
            if pairs
            else None,
            "cohen_kappa_three_class": _cohen_kappa(a, b),
            "disagreement_counts": {
                f"{left}_to_{right}": count
                for (left, right), count in sorted(
                    Counter(pair for pair in pairs if pair[0] != pair[1]).items()
                )
            },
        }

    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        **metrics(all_pairs),
        "strata": [
            {"candidate_topic": topic, "selection_mode": mode, **metrics(pairs)}
            for (topic, mode), pairs in sorted(by_topic_mode.items())
        ],
        "sha256": hashes,
        "release_class": "aggregate-only-annotation-agreement",
    }
    manifest_path = repo_root / config.manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
