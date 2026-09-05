from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from enum import StrEnum
from itertools import pairwise
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

REGISTRY_SCHEMA_VERSION = "1.0"


class IdentifierType(StrEnum):
    CIK = "cik"
    TICKER = "ticker"
    LEGAL_NAME = "legal_name"
    PROVIDER_ID = "provider_id"


class CompanyIdentifier(BaseModel):
    """One effective-dated company identifier or name."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = REGISTRY_SCHEMA_VERSION
    company_id: str = Field(min_length=1)
    identifier_type: IdentifierType
    identifier_value: str = Field(min_length=1)
    valid_from: date
    valid_to: date | None = None
    source_id: str = Field(min_length=1)
    overlap_exception_reason: str | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        return self


class FiscalPeriod(BaseModel):
    """Canonical company fiscal quarter and its point-in-time event timestamps."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = REGISTRY_SCHEMA_VERSION
    company_id: str = Field(min_length=1)
    fiscal_year: int = Field(ge=1900, le=2200)
    fiscal_quarter: int = Field(ge=1, le=4)
    period_start: date
    period_end: date
    earnings_release_at: datetime | None = None
    call_id: str | None = None
    call_started_at: datetime | None = None
    filing_accepted_at: datetime | None = None
    mapping_source: str = Field(min_length=1)
    mapping_exception_reason: str | None = None

    @model_validator(mode="after")
    def validate_dates_and_call(self) -> Self:
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        if (self.call_id is None) != (self.call_started_at is None):
            raise ValueError("call_id and call_started_at must either both be set or both be null")
        timestamps = (self.earnings_release_at, self.call_started_at, self.filing_accepted_at)
        if any(value is not None and value.tzinfo is None for value in timestamps):
            raise ValueError("event timestamps must be timezone-aware")
        if (
            self.call_started_at is not None
            and self.call_started_at.date() < self.period_end
            and not self.mapping_exception_reason
        ):
            raise ValueError("a call before period_end requires mapping_exception_reason")
        return self


def _overlap(left: CompanyIdentifier, right: CompanyIdentifier) -> bool:
    left_end = left.valid_to or date.max
    return right.valid_from <= left_end


def validate_identifiers(records: list[CompanyIdentifier]) -> None:
    """Enforce one active value per company and identifier type unless explicitly excepted."""
    groups: dict[tuple[str, IdentifierType], list[CompanyIdentifier]] = defaultdict(list)
    for record in records:
        groups[(record.company_id, record.identifier_type)].append(record)

    for key, group in groups.items():
        ordered = sorted(group, key=lambda item: (item.valid_from, item.identifier_value))
        for left, right in pairwise(ordered):
            if _overlap(left, right) and not (
                left.overlap_exception_reason and right.overlap_exception_reason
            ):
                raise ValueError(f"Overlapping identifier intervals for {key[0]} / {key[1]}")


def validate_fiscal_periods(records: list[FiscalPeriod]) -> None:
    """Enforce canonical-quarter uniqueness, non-overlap, and one-quarter-per-call."""
    quarter_keys: set[tuple[str, int, int]] = set()
    call_keys: set[str] = set()
    company_periods: dict[str, list[FiscalPeriod]] = defaultdict(list)
    for record in records:
        quarter_key = (record.company_id, record.fiscal_year, record.fiscal_quarter)
        if quarter_key in quarter_keys:
            raise ValueError(f"Duplicate canonical fiscal quarter: {quarter_key}")
        quarter_keys.add(quarter_key)
        if record.call_id is not None:
            if record.call_id in call_keys:
                raise ValueError(f"Call maps to multiple fiscal quarters: {record.call_id}")
            call_keys.add(record.call_id)
        company_periods[record.company_id].append(record)

    for company_id, periods in company_periods.items():
        ordered = sorted(periods, key=lambda item: item.period_start)
        for left, right in pairwise(ordered):
            if right.period_start <= left.period_end:
                raise ValueError(f"Overlapping fiscal periods for {company_id}")
