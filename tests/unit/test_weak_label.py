from cnbr.transcripts.weak_label import parse_verdict


def test_parse_verdict_is_case_insensitive() -> None:
    assert parse_verdict("Answer: YES") == "yes"


def test_parse_verdict_rejects_non_verdict_response() -> None:
    assert parse_verdict("I cannot decide.") == "unparseable"
