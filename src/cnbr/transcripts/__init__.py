"""Transcript normalization and quality-audit operations."""

from cnbr.transcripts.annotation import build_annotation_pilot
from cnbr.transcripts.annotation_review import review_annotation_exports
from cnbr.transcripts.audit import build_transcript_audit
from cnbr.transcripts.features import build_narrative_structure_features
from cnbr.transcripts.lexical import build_lexical_baseline
from cnbr.transcripts.normalize import normalize_transcripts
from cnbr.transcripts.weak_label import (
    run_hosted_weak_label_calibration,
    run_local_gguf_weak_label_calibration,
    run_local_weak_label_benchmark,
)

__all__ = [
    "build_annotation_pilot",
    "build_lexical_baseline",
    "build_narrative_structure_features",
    "build_transcript_audit",
    "normalize_transcripts",
    "review_annotation_exports",
    "run_hosted_weak_label_calibration",
    "run_local_gguf_weak_label_calibration",
    "run_local_weak_label_benchmark",
]
