from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from cnbr.config import load_synthetic_config, load_universe_config
from cnbr.logging import configure_logging
from cnbr.registry import build_company_universe
from cnbr.synthetic import run_synthetic_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cnbr")
    subparsers = parser.add_subparsers(dest="command", required=True)
    synthetic = subparsers.add_parser("synthetic-run", help="Run the Stage 0 synthetic pipeline")
    synthetic.add_argument("--config", type=Path, required=True)
    universe = subparsers.add_parser(
        "universe-build", help="Acquire and build a point-in-time company universe"
    )
    universe.add_argument("--config", type=Path, required=True)
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
