from cnbr.cli import build_parser


def test_cli_parses_synthetic_command() -> None:
    args = build_parser().parse_args(["synthetic-run", "--config", "config.yaml"])
    assert args.command == "synthetic-run"
    assert args.config.name == "config.yaml"


def test_cli_parses_hosted_weak_label_command() -> None:
    args = build_parser().parse_args(["hosted-weak-label", "--config", "config.yaml"])
    assert args.command == "hosted-weak-label"


def test_cli_parses_local_gguf_weak_label_command() -> None:
    args = build_parser().parse_args(["local-gguf-weak-label", "--config", "config.yaml"])
    assert args.command == "local-gguf-weak-label"
