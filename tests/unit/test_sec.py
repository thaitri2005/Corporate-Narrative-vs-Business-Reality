from __future__ import annotations

import httpx
import pytest

from cnbr.sources.sec import SecClient, validate_sec_user_agent


@pytest.mark.parametrize(
    "identity",
    ["anonymous", "Researcher Name contact@example.com", "No Email Organization"],
)
def test_sec_user_agent_rejects_missing_or_placeholder_identity(identity: str) -> None:
    with pytest.raises(ValueError, match="SEC User-Agent"):
        validate_sec_user_agent(identity)


def test_sec_client_normalizes_cik_and_identifies_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/submissions/CIK0000021344.json"
        assert request.headers["User-Agent"] == "CNBR Research team@organization.org"
        return httpx.Response(200, json={"cik": "21344"}, request=request)

    with SecClient(
        "CNBR Research team@organization.org", transport=httpx.MockTransport(handler)
    ) as client:
        payload = client.submissions("21344")

    assert payload["cik"] == "21344"


def test_sec_client_rejects_invalid_cik_before_request() -> None:
    def should_not_run(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected request: {request.url}")

    with (
        SecClient(
            "CNBR Research team@organization.org", transport=httpx.MockTransport(should_not_run)
        ) as client,
        pytest.raises(ValueError, match="Invalid SEC CIK"),
    ):
        client.company_facts("not-a-cik")
