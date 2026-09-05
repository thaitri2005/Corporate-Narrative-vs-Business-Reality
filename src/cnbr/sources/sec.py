from __future__ import annotations

import re
from typing import Any, Final, cast

import httpx

SEC_BASE_URL: Final[str] = "https://data.sec.gov"
EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
PLACEHOLDERS: Final[tuple[str, ...]] = ("example.com", "your name", "researcher name")


def validate_sec_user_agent(value: str) -> str:
    """Reject anonymous or placeholder identities before any SEC request is made."""
    normalized = " ".join(value.split())
    lowered = normalized.lower()
    if len(normalized) < 12 or EMAIL_PATTERN.search(normalized) is None:
        raise ValueError("SEC User-Agent must contain a name/organization and contact email")
    if any(marker in lowered for marker in PLACEHOLDERS):
        raise ValueError("SEC User-Agent contains a placeholder identity")
    return normalized


class SecClient:
    """Small SEC JSON adapter with mandatory truthful request identification."""

    def __init__(
        self,
        user_agent: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        identity = validate_sec_user_agent(user_agent)
        self._client = httpx.Client(
            base_url=SEC_BASE_URL,
            headers={"User-Agent": identity, "Accept-Encoding": "gzip, deflate"},
            timeout=timeout_seconds,
            transport=transport,
        )

    def __enter__(self) -> SecClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def submissions(self, cik: str) -> dict[str, Any]:
        return self._get_json(f"/submissions/CIK{self._normalize_cik(cik)}.json")

    def company_facts(self, cik: str) -> dict[str, Any]:
        return self._get_json(f"/api/xbrl/companyfacts/CIK{self._normalize_cik(cik)}.json")

    @staticmethod
    def _normalize_cik(cik: str) -> str:
        stripped = cik.strip()
        if not stripped.isdigit() or len(stripped) > 10:
            raise ValueError(f"Invalid SEC CIK: {cik!r}")
        return stripped.zfill(10)

    def _get_json(self, path: str) -> dict[str, Any]:
        response = self._client.get(path)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object from SEC endpoint {path}")
        return cast(dict[str, Any], payload)
