from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Final, cast

import httpx

SEC_BASE_URL: Final[str] = "https://data.sec.gov"
EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
PLACEHOLDERS: Final[tuple[str, ...]] = ("example.com", "your name", "researcher name")
HISTORY_FILE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^CIK\d{10}-submissions-\d{3}\.json$")
RETRYABLE_STATUS: Final[set[int]] = {429, 500, 502, 503, 504}


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
        requests_per_second: float = 8.0,
        max_attempts: int = 4,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        identity = validate_sec_user_agent(user_agent)
        if not 0 < requests_per_second <= 8:
            raise ValueError("requests_per_second must be greater than 0 and no more than 8")
        if not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        self._client = httpx.Client(
            base_url=SEC_BASE_URL,
            headers={"User-Agent": identity, "Accept-Encoding": "gzip, deflate"},
            timeout=timeout_seconds,
            transport=transport,
        )
        self._minimum_interval = 1.0 / requests_per_second
        self._max_attempts = max_attempts
        self._clock = clock
        self._sleeper = sleeper
        self._rate_lock = threading.Lock()
        self._last_request_started: float | None = None

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

    def artifact_bytes(self, kind: str, cik: str) -> tuple[str, bytes]:
        normalized_cik = self._normalize_cik(cik)
        if kind == "submissions":
            path = f"/submissions/CIK{normalized_cik}.json"
        elif kind == "companyfacts":
            path = f"/api/xbrl/companyfacts/CIK{normalized_cik}.json"
        else:
            raise ValueError(f"Unsupported SEC artifact kind: {kind!r}")
        response = self._get(path)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object from SEC endpoint {path}")
        return str(response.url), response.content

    def submission_history_bytes(self, filename: str) -> tuple[str, bytes]:
        if HISTORY_FILE_PATTERN.fullmatch(filename) is None:
            raise ValueError(f"Invalid SEC submission-history filename: {filename!r}")
        path = f"/submissions/{filename}"
        response = self._get(path)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object from SEC endpoint {path}")
        return str(response.url), response.content

    @staticmethod
    def _normalize_cik(cik: str) -> str:
        stripped = cik.strip()
        if not stripped.isdigit() or len(stripped) > 10:
            raise ValueError(f"Invalid SEC CIK: {cik!r}")
        return stripped.zfill(10)

    def _get_json(self, path: str) -> dict[str, Any]:
        response = self._get(path)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object from SEC endpoint {path}")
        return cast(dict[str, Any], payload)

    def _get(self, path: str) -> httpx.Response:
        for attempt in range(self._max_attempts):
            self._wait_for_rate_slot()
            response = self._client.get(path)
            if response.status_code not in RETRYABLE_STATUS or attempt + 1 == self._max_attempts:
                response.raise_for_status()
                return response
            retry_after = response.headers.get("Retry-After")
            delay = min(8.0, 0.5 * (2**attempt))
            if retry_after is not None:
                with suppress(ValueError):
                    delay = max(delay, min(30.0, float(retry_after)))
            self._sleeper(delay)
        raise AssertionError("bounded SEC retry loop exhausted unexpectedly")

    def _wait_for_rate_slot(self) -> None:
        with self._rate_lock:
            now = self._clock()
            if self._last_request_started is not None:
                remaining = self._minimum_interval - (now - self._last_request_started)
                if remaining > 0:
                    self._sleeper(remaining)
            self._last_request_started = self._clock()
