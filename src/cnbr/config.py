from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SyntheticConfig(BaseModel):
    """Validated configuration for the Stage 0 synthetic pipeline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    seed: int = Field(ge=0)
    input_path: Path
    interim_path: Path
    feature_path: Path
    summary_path: Path
    run_manifest_path: Path

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class UniverseConfig(BaseModel):
    """Validated configuration for a point-in-time company-universe snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    source_id: str
    source_url: str
    source_revision: str
    source_license: str
    snapshot_date: date
    sector: str = "Consumer Staples"
    raw_path: Path
    curated_path: Path
    manifest_path: Path

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class SecCompanyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cik: str = Field(pattern=r"^\d{1,10}$")
    ticker: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class SecSpikeConfig(BaseModel):
    """Bounded SEC feasibility-spike configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    companies: list[SecCompanyConfig] = Field(min_length=1, max_length=5)
    max_workers: int = Field(default=3, ge=1, le=3)
    requests_per_second: float = Field(default=8.0, gt=0, le=8.0)
    max_attempts: int = Field(default=4, ge=1, le=5)
    study_start: date
    study_end: date
    output_dir: Path
    manifest_path: Path

    @model_validator(mode="after")
    def validate_study_dates(self) -> SecSpikeConfig:
        if self.study_end < self.study_start:
            raise ValueError("study_end must be on or after study_start")
        return self

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class ConceptFamilyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    concepts: list[str] = Field(min_length=1)
    expected_periods: int = Field(default=32, ge=1)


class SecCoverageConfig(BaseModel):
    """Configuration for a local Company Facts concept-coverage audit."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    start_fiscal_year: int = Field(ge=1900, le=2200)
    end_fiscal_year: int = Field(ge=1900, le=2200)
    input_dir: Path
    detail_path: Path
    summary_path: Path
    concepts: dict[str, ConceptFamilyConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_years(self) -> SecCoverageConfig:
        if self.end_fiscal_year < self.start_fiscal_year:
            raise ValueError("end_fiscal_year must be on or after start_fiscal_year")
        return self

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class SecFilingIndexConfig(BaseModel):
    """Configuration for a local SEC filing/time spine."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    study_start: date
    study_end: date
    input_dir: Path
    output_path: Path
    summary_path: Path

    @model_validator(mode="after")
    def validate_study_dates(self) -> SecFilingIndexConfig:
        if self.study_end < self.study_start:
            raise ValueError("study_end must be on or after study_start")
        return self

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class StruxSourceFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_path: Path


class StruxIngestionConfig(BaseModel):
    """Restricted local STRUX acquisition and universe-filter configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    source_revision: str
    sources: list[StruxSourceFile] = Field(min_length=1)
    universe_path: Path
    output_path: Path
    manifest_path: Path
    rights_policy: str = "personal-local-risk-accepted"

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class TranscriptAuditConfig(BaseModel):
    """Local transcript coverage and structural-quality audit configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    input_path: Path
    call_detail_path: Path
    company_summary_path: Path
    manifest_path: Path
    minimum_calls: int = Field(default=12, ge=1)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class TranscriptNormalizeConfig(BaseModel):
    """Configuration for deterministic STRUX-to-canonical transcript normalization."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    source_revision: str
    input_path: Path
    universe_path: Path
    calls_path: Path
    participants_path: Path
    utterances_path: Path
    manifest_path: Path
    role_by_position: dict[str, str]
    duplicate_minimum_words: int = Field(default=20, ge=1)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class FiscalAlignmentConfig(BaseModel):
    """Configuration for the accession-bound fiscal spine and call mapping thin slice."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.0"
    companies: list[str] = Field(min_length=1)
    filing_index_path: Path
    calls_path: Path
    universe_path: Path
    sec_raw_dir: Path
    fiscal_periods_path: Path
    call_mappings_path: Path
    manifest_path: Path
    maximum_call_lag_days: int = Field(default=75, ge=1, le=120)
    period_boundary_concepts: list[str] = Field(min_length=1)
    review_excluded_call_ids: list[str] = Field(default_factory=list)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class FinancialExtractConfig(BaseModel):
    """Configuration for accession-bound long-form SEC fact extraction."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    companies: list[str] = Field(min_length=1)
    filing_index_path: Path
    universe_path: Path
    sec_raw_dir: Path
    output_path: Path
    manifest_path: Path
    metric_concepts: dict[str, list[str]] = Field(min_length=1)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class FinancialNormalizeConfig(BaseModel):
    """Configuration for canonical quarterly financial-value resolution."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    occurrence_path: Path
    fiscal_periods_path: Path
    filing_index_path: Path
    universe_path: Path
    output_path: Path
    manifest_path: Path
    metric_concepts: dict[str, list[str]] = Field(min_length=1)
    revenue_priority_by_ticker: dict[str, list[str]] = Field(min_length=1)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class FinancialFeatureConfig(BaseModel):
    """Configuration for deterministic thin-slice financial feature derivation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    input_path: Path
    output_path: Path
    manifest_path: Path

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class FinancialReconciliationConfig(BaseModel):
    """Configuration for local arithmetic and provenance reconciliation of canonical values."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    values_path: Path
    occurrence_path: Path
    detail_path: Path
    manifest_path: Path
    samples_per_formula_ticker: int = Field(default=3, ge=1, le=5)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class NarrativeFeatureConfig(BaseModel):
    """Configuration for role-aware, non-semantic transcript structure features."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    utterances_path: Path
    call_mappings_path: Path
    output_path: Path
    manifest_path: Path
    excluded_quality_flags: list[str]

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class LexicalTopicDefinition(BaseModel):
    """A transparent, versioned discovery dictionary; never a ground-truth label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    topic_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    display_name: str = Field(min_length=1)
    patterns: list[str] = Field(min_length=1)


class LexicalBaselineConfig(BaseModel):
    """Configuration for local-only dictionary topic discovery features."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "0.1"
    taxonomy_version: str
    utterances_path: Path
    call_mappings_path: Path
    output_path: Path
    manifest_path: Path
    excluded_quality_flags: list[str]
    views: list[str] = Field(min_length=1)
    topics: list[LexicalTopicDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_topic_ids(self) -> LexicalBaselineConfig:
        if len({topic.topic_id for topic in self.topics}) != len(self.topics):
            raise ValueError("Lexical topic IDs must be unique")
        return self

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class PanelBuildConfig(BaseModel):
    """Configuration for the frozen-key analytical thin-slice panel."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    narrative_path: Path
    financial_path: Path
    output_path: Path
    manifest_path: Path
    current_financial_metrics: list[str]
    lead_outcome_metrics: list[str]

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class FiscalReviewConfig(BaseModel):
    """Configuration for a restricted local fiscal-mapping review packet."""

    model_config = ConfigDict(extra="forbid")

    mappings_path: Path
    utterances_path: Path
    html_path: Path
    checklist_path: Path
    samples_per_company: int = Field(default=3, ge=1, le=5)
    excerpt_characters: int = Field(default=2000, ge=500, le=5000)


def load_synthetic_config(path: Path) -> SyntheticConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return SyntheticConfig.model_validate(raw)


def load_universe_config(path: Path) -> UniverseConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return UniverseConfig.model_validate(raw)


def load_sec_spike_config(path: Path) -> SecSpikeConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return SecSpikeConfig.model_validate(raw)


def load_sec_coverage_config(path: Path) -> SecCoverageConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return SecCoverageConfig.model_validate(raw)


def load_sec_filing_index_config(path: Path) -> SecFilingIndexConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return SecFilingIndexConfig.model_validate(raw)


def load_strux_ingestion_config(path: Path) -> StruxIngestionConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return StruxIngestionConfig.model_validate(raw)


def load_transcript_audit_config(path: Path) -> TranscriptAuditConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return TranscriptAuditConfig.model_validate(raw)


def load_transcript_normalize_config(path: Path) -> TranscriptNormalizeConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return TranscriptNormalizeConfig.model_validate(raw)


def load_fiscal_alignment_config(path: Path) -> FiscalAlignmentConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return FiscalAlignmentConfig.model_validate(raw)


def load_financial_extract_config(path: Path) -> FinancialExtractConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return FinancialExtractConfig.model_validate(raw)


def load_financial_normalize_config(path: Path) -> FinancialNormalizeConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return FinancialNormalizeConfig.model_validate(raw)


def load_financial_feature_config(path: Path) -> FinancialFeatureConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return FinancialFeatureConfig.model_validate(raw)


def load_financial_reconciliation_config(path: Path) -> FinancialReconciliationConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return FinancialReconciliationConfig.model_validate(raw)


def load_narrative_feature_config(path: Path) -> NarrativeFeatureConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return NarrativeFeatureConfig.model_validate(raw)


def load_lexical_baseline_config(path: Path) -> LexicalBaselineConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return LexicalBaselineConfig.model_validate(raw)


def load_panel_build_config(path: Path) -> PanelBuildConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return PanelBuildConfig.model_validate(raw)


def load_fiscal_review_config(path: Path) -> FiscalReviewConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return FiscalReviewConfig.model_validate(raw)
