from pathlib import Path

from cnbr.transcripts.weak_label import _get_hf_token, parse_json_verdict, parse_verdict


def test_parse_verdict_is_case_insensitive() -> None:
    assert parse_verdict("Answer: YES") == "yes"


def test_parse_verdict_rejects_non_verdict_response() -> None:
    assert parse_verdict("I cannot decide.") == "unparseable"


def test_parse_json_verdict_requires_the_contract() -> None:
    assert parse_json_verdict('{"verdict":"no"}') == "no"
    assert parse_json_verdict("verdict: no") == "unparseable"


def test_parse_json_verdict_ignores_llama_cli_wrapper() -> None:
    wrapped = 'llama.cpp banner\n> prompt\n{"verdict":"yes"}\n[ timing ]'
    assert parse_json_verdict(wrapped) == "yes"


def test_parse_json_verdict_rejects_extra_fields() -> None:
    assert parse_json_verdict('{"verdict":"yes","reason":"maybe"}') == "unparseable"


def test_hf_token_prefers_environment(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HF_TOKEN", "environment-token")
    (tmp_path / ".env").write_text("HF_TOKEN=file-token\n", encoding="utf-8")
    assert _get_hf_token(tmp_path) == "environment-token"


def test_hf_token_reads_ignored_env_file(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("HF_TOKEN", raising=False)
    (tmp_path / ".env").write_text("# local only\nHF_TOKEN='file-token'\n", encoding="utf-8")
    assert _get_hf_token(tmp_path) == "file-token"
