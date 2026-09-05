from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from cnbr.analysis import build_thin_slice_panel
from cnbr.config import (
    load_annotation_pilot_config,
    load_financial_extract_config,
    load_financial_feature_config,
    load_financial_normalize_config,
    load_financial_reconciliation_config,
    load_fiscal_alignment_config,
    load_fiscal_review_config,
    load_lexical_baseline_config,
    load_narrative_feature_config,
    load_panel_build_config,
    load_sec_coverage_config,
    load_sec_filing_index_config,
    load_sec_spike_config,
    load_strux_ingestion_config,
    load_synthetic_config,
    load_transcript_audit_config,
    load_transcript_normalize_config,
    load_universe_config,
    load_weak_label_config,
)
from cnbr.financials import (
    build_concept_coverage,
    build_filing_index,
    build_financial_features,
    build_fiscal_alignment,
    extract_financial_facts,
    normalize_financial_values,
    reconcile_financial_values,
)
from cnbr.logging import configure_logging
from cnbr.registry import build_company_universe
from cnbr.review import build_fiscal_review_packet
from cnbr.sources import ingest_strux_subset, run_sec_spike
from cnbr.synthetic import run_synthetic_pipeline
from cnbr.transcripts import (
    build_annotation_pilot,
    build_lexical_baseline,
    build_narrative_structure_features,
    build_transcript_audit,
    normalize_transcripts,
    run_local_weak_label_benchmark,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cnbr")
    subparsers = parser.add_subparsers(dest="command", required=True)
    synthetic = subparsers.add_parser("synthetic-run", help="Run the Stage 0 synthetic pipeline")
    synthetic.add_argument("--config", type=Path, required=True)
    universe = subparsers.add_parser(
        "universe-build", help="Acquire and build a point-in-time company universe"
    )
    universe.add_argument("--config", type=Path, required=True)
    sec_spike = subparsers.add_parser(
        "sec-spike", help="Run the bounded Stage 1 SEC feasibility acquisition"
    )
    sec_spike.add_argument("--config", type=Path, required=True)
    sec_coverage = subparsers.add_parser(
        "sec-coverage", help="Measure local SEC Company Facts concept availability"
    )
    sec_coverage.add_argument("--config", type=Path, required=True)
    filing_index = subparsers.add_parser(
        "sec-filing-index", help="Build the local SEC filing and acceptance-time spine"
    )
    filing_index.add_argument("--config", type=Path, required=True)
    strux = subparsers.add_parser(
        "strux-ingest", help="Acquire and locally filter the restricted STRUX full split"
    )
    strux.add_argument("--config", type=Path, required=True)
    transcript_audit = subparsers.add_parser(
        "transcript-audit", help="Profile local transcript coverage and structural quality"
    )
    transcript_audit.add_argument("--config", type=Path, required=True)
    transcript_normalize = subparsers.add_parser(
        "transcript-normalize", help="Normalize local STRUX calls into canonical transcript tables"
    )
    transcript_normalize.add_argument("--config", type=Path, required=True)
    fiscal_align = subparsers.add_parser(
        "fiscal-align", help="Build an accession-bound fiscal spine and map date-precision calls"
    )
    fiscal_align.add_argument("--config", type=Path, required=True)
    financial_extract = subparsers.add_parser(
        "financial-extract", help="Extract accession-bound long-form SEC fact occurrences"
    )
    financial_extract.add_argument("--config", type=Path, required=True)
    financial_normalize = subparsers.add_parser(
        "financial-normalize", help="Resolve canonical quarterly financial values"
    )
    financial_normalize.add_argument("--config", type=Path, required=True)
    financial_features = subparsers.add_parser(
        "financial-features", help="Derive transparent quarterly financial features"
    )
    financial_features.add_argument("--config", type=Path, required=True)
    financial_reconcile = subparsers.add_parser(
        "financial-reconcile", help="Audit canonical financial values against stored operands"
    )
    financial_reconcile.add_argument("--config", type=Path, required=True)
    narrative_features = subparsers.add_parser(
        "narrative-features", help="Derive role-aware non-semantic transcript structure features"
    )
    narrative_features.add_argument("--config", type=Path, required=True)
    lexical_baseline = subparsers.add_parser(
        "lexical-baseline", help="Build local, non-confirmatory lexical discovery features"
    )
    lexical_baseline.add_argument("--config", type=Path, required=True)
    annotation_pilot = subparsers.add_parser(
        "annotation-pilot", help="Create restricted local annotation-pilot tasks"
    )
    annotation_pilot.add_argument("--config", type=Path, required=True)
    weak_label = subparsers.add_parser(
        "weak-label", help="Benchmark a local pinned LLM against human labels"
    )
    weak_label.add_argument("--config", type=Path, required=True)
    panel_build = subparsers.add_parser(
        "panel-build", help="Build the point-in-time analytical thin-slice panel"
    )
    panel_build.add_argument("--config", type=Path, required=True)
    fiscal_review = subparsers.add_parser(
        "fiscal-review-build", help="Create a restricted local fiscal-mapping review packet"
    )
    fiscal_review.add_argument("--config", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    configure_logging()
    args = build_parser().parse_args(argv)
    if args.command == "synthetic-run":
        config_path: Path = args.config.resolve()
        config = load_synthetic_config(config_path)
        run_synthetic_pipeline(config, Path.cwd().resolve())
    elif args.command == "universe-build":
        config_path = args.config.resolve()
        universe_config = load_universe_config(config_path)
        build_company_universe(universe_config, Path.cwd().resolve())
    elif args.command == "sec-spike":
        config_path = args.config.resolve()
        sec_config = load_sec_spike_config(config_path)
        user_agent = os.environ.get("CNBR_SEC_USER_AGENT")
        if user_agent is None:
            raise RuntimeError("CNBR_SEC_USER_AGENT is required for SEC requests")
        run_sec_spike(sec_config, Path.cwd().resolve(), user_agent)
    elif args.command == "sec-coverage":
        config_path = args.config.resolve()
        coverage_config = load_sec_coverage_config(config_path)
        build_concept_coverage(coverage_config, Path.cwd().resolve())
    elif args.command == "sec-filing-index":
        config_path = args.config.resolve()
        filing_config = load_sec_filing_index_config(config_path)
        build_filing_index(filing_config, Path.cwd().resolve())
    elif args.command == "strux-ingest":
        config_path = args.config.resolve()
        strux_config = load_strux_ingestion_config(config_path)
        ingest_strux_subset(strux_config, Path.cwd().resolve())
    elif args.command == "transcript-audit":
        config_path = args.config.resolve()
        audit_config = load_transcript_audit_config(config_path)
        build_transcript_audit(audit_config, Path.cwd().resolve())
    elif args.command == "transcript-normalize":
        config_path = args.config.resolve()
        normalize_config = load_transcript_normalize_config(config_path)
        normalize_transcripts(normalize_config, Path.cwd().resolve())
    elif args.command == "fiscal-align":
        config_path = args.config.resolve()
        alignment_config = load_fiscal_alignment_config(config_path)
        build_fiscal_alignment(alignment_config, Path.cwd().resolve())
    elif args.command == "financial-extract":
        config_path = args.config.resolve()
        extract_config = load_financial_extract_config(config_path)
        extract_financial_facts(extract_config, Path.cwd().resolve())
    elif args.command == "financial-normalize":
        config_path = args.config.resolve()
        financial_config = load_financial_normalize_config(config_path)
        normalize_financial_values(financial_config, Path.cwd().resolve())
    elif args.command == "financial-features":
        config_path = args.config.resolve()
        feature_config = load_financial_feature_config(config_path)
        build_financial_features(feature_config, Path.cwd().resolve())
    elif args.command == "financial-reconcile":
        config_path = args.config.resolve()
        reconciliation_config = load_financial_reconciliation_config(config_path)
        reconcile_financial_values(reconciliation_config, Path.cwd().resolve())
    elif args.command == "narrative-features":
        config_path = args.config.resolve()
        narrative_config = load_narrative_feature_config(config_path)
        build_narrative_structure_features(narrative_config, Path.cwd().resolve())
    elif args.command == "lexical-baseline":
        config_path = args.config.resolve()
        lexical_config = load_lexical_baseline_config(config_path)
        build_lexical_baseline(lexical_config, Path.cwd().resolve())
    elif args.command == "annotation-pilot":
        config_path = args.config.resolve()
        annotation_config = load_annotation_pilot_config(config_path)
        build_annotation_pilot(annotation_config, Path.cwd().resolve())
    elif args.command == "weak-label":
        config_path = args.config.resolve()
        weak_config = load_weak_label_config(config_path)
        run_local_weak_label_benchmark(weak_config, Path.cwd().resolve())
    elif args.command == "panel-build":
        config_path = args.config.resolve()
        panel_config = load_panel_build_config(config_path)
        build_thin_slice_panel(panel_config, Path.cwd().resolve())
    elif args.command == "fiscal-review-build":
        config_path = args.config.resolve()
        review_config = load_fiscal_review_config(config_path)
        build_fiscal_review_packet(review_config, Path.cwd().resolve())
