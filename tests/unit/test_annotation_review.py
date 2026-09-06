from __future__ import annotations

import json
from pathlib import Path

import pytest

from cnbr.config import AnnotationAgreementConfig, AnnotationReviewConfig
from cnbr.transcripts import measure_annotation_agreement, review_annotation_exports


def _write_pair(root: Path, suffix: str, mode: str, verdict: str) -> tuple[Path, Path]:
    task_path = root / f"tasks-{suffix}.json"
    label_path = root / f"labels-{suffix}.json"
    task_path.write_text(
        json.dumps(
            [
                {
                    "data": {
                        "task_id": f"id-{suffix}",
                        "candidate_topic": "pricing",
                        "selection_mode": mode,
                        "text": "restricted text",
                    }
                }
            ]
        ),
        encoding="utf-8",
    )
    label_path.write_text(
        json.dumps(
            [{"task_id": f"id-{suffix}", "candidate_topic": "pricing", "verdict": verdict}],
        ),
        encoding="utf-8",
    )
    return task_path, label_path


def test_annotation_review_writes_text_free_aggregate_manifest(tmp_path: Path) -> None:
    task_a, label_a = _write_pair(tmp_path, "a", "lexical_match", "yes")
    task_b, label_b = _write_pair(tmp_path, "b", "lexical_nonmatch", "no")
    result = review_annotation_exports(
        AnnotationReviewConfig(
            task_paths=[task_a.relative_to(tmp_path), task_b.relative_to(tmp_path)],
            label_paths=[label_a.relative_to(tmp_path), label_b.relative_to(tmp_path)],
            manifest_path=Path("reports/review.json"),
        ),
        tmp_path,
    )

    manifest = (tmp_path / "reports/review.json").read_text(encoding="utf-8")
    assert result["task_count"] == 2
    assert result["verdict_counts"] == {"no": 1, "unsure": 0, "yes": 1}
    assert "restricted text" not in manifest
    assert '"release_class": "aggregate-only-annotation-review"' in manifest


def test_annotation_review_rejects_mismatched_task_ids(tmp_path: Path) -> None:
    task, label = _write_pair(tmp_path, "a", "lexical_match", "yes")
    label.write_text(json.dumps([{"task_id": "other", "verdict": "yes"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="Task/label IDs differ"):
        review_annotation_exports(
            AnnotationReviewConfig(
                task_paths=[task.relative_to(tmp_path)],
                label_paths=[label.relative_to(tmp_path)],
                manifest_path=Path("reports/review.json"),
            ),
            tmp_path,
        )


def test_annotation_agreement_writes_aggregate_only_metrics(tmp_path: Path) -> None:
    task_a, label_a = _write_pair(tmp_path, "a", "lexical_match", "yes")
    task_b, label_b = _write_pair(tmp_path, "b", "lexical_nonmatch", "no")
    label_a_second = tmp_path / "labels-a-second.json"
    label_b_second = tmp_path / "labels-b-second.json"
    label_a_second.write_text(json.dumps([{"task_id": "id-a", "verdict": "yes"}]), encoding="utf-8")
    label_b_second.write_text(
        json.dumps([{"task_id": "id-b", "verdict": "unsure"}]), encoding="utf-8"
    )

    result = measure_annotation_agreement(
        AnnotationAgreementConfig(
            task_paths=[task_a.relative_to(tmp_path), task_b.relative_to(tmp_path)],
            reviewer_a_label_paths=[label_a.relative_to(tmp_path), label_b.relative_to(tmp_path)],
            reviewer_b_label_paths=[
                label_a_second.relative_to(tmp_path),
                label_b_second.relative_to(tmp_path),
            ],
            manifest_path=Path("reports/agreement.json"),
        ),
        tmp_path,
    )

    manifest = (tmp_path / "reports/agreement.json").read_text(encoding="utf-8")
    assert result["task_count"] == 2
    assert result["exact_agreement"] == 0.5
    assert "restricted text" not in manifest
    assert '"release_class": "aggregate-only-annotation-agreement"' in manifest
