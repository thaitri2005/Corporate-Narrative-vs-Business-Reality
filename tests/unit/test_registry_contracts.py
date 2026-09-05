from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from pydantic import ValidationError

from cnbr.contracts.registry import (
    CompanyIdentifier,
    FiscalPeriod,
    IdentifierType,
    validate_fiscal_periods,
    validate_identifiers,
)


def _identifier(value: str, start: date, end: date | None = None) -> CompanyIdentifier:
    return CompanyIdentifier(
        company_id="sec-cik-0000000001",
        identifier_type=IdentifierType.TICKER,
        identifier_value=value,
        valid_from=start,
        valid_to=end,
        source_id="golden-fixture",
    )


def _period(
    quarter: int,
    start: date,
    end: date,
    *,
    call_id: str | None = None,
) -> FiscalPeriod:
    call_at = datetime.combine(end + timedelta(days=10), time(12), tzinfo=UTC) if call_id else None
    return FiscalPeriod(
        company_id="sec-cik-0000000001",
        fiscal_year=2025,
        fiscal_quarter=quarter,
        period_start=start,
        period_end=end,
        call_id=call_id,
        call_started_at=call_at,
        mapping_source="golden-fixture",
    )


def test_non_overlapping_ticker_change_is_valid() -> None:
    records = [
        _identifier("OLD", date(2020, 1, 1), date(2023, 12, 31)),
        _identifier("NEW", date(2024, 1, 1)),
    ]
    validate_identifiers(records)


def test_overlapping_identifiers_fail_closed() -> None:
    records = [
        _identifier("OLD", date(2020, 1, 1), date(2024, 1, 2)),
        _identifier("NEW", date(2024, 1, 1)),
    ]
    with pytest.raises(ValueError, match="Overlapping identifier"):
        validate_identifiers(records)


def test_missing_call_is_valid_but_partial_call_mapping_is_not() -> None:
    missing_call = _period(1, date(2025, 1, 1), date(2025, 3, 31))
    validate_fiscal_periods([missing_call])

    with pytest.raises(ValidationError, match="call_id and call_started_at"):
        FiscalPeriod(
            company_id="sec-cik-0000000001",
            fiscal_year=2025,
            fiscal_quarter=1,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 3, 31),
            call_id="call-1",
            mapping_source="golden-fixture",
        )


def test_call_cannot_map_to_two_quarters() -> None:
    records = [
        _period(1, date(2025, 1, 1), date(2025, 3, 31), call_id="call-1"),
        _period(2, date(2025, 4, 1), date(2025, 6, 30), call_id="call-1"),
    ]
    with pytest.raises(ValueError, match="multiple fiscal quarters"):
        validate_fiscal_periods(records)


def test_non_calendar_periods_validate_and_overlaps_fail() -> None:
    valid = [
        _period(1, date(2024, 10, 1), date(2024, 12, 31)),
        _period(2, date(2025, 1, 1), date(2025, 3, 31)),
    ]
    validate_fiscal_periods(valid)

    overlap = _period(3, date(2025, 3, 31), date(2025, 6, 30))
    with pytest.raises(ValueError, match="Overlapping fiscal periods"):
        validate_fiscal_periods([*valid, overlap])
