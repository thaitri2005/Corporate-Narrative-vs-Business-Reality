from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


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
    output_dir: Path
    manifest_path: Path

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


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
