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


def load_synthetic_config(path: Path) -> SyntheticConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return SyntheticConfig.model_validate(raw)


def load_universe_config(path: Path) -> UniverseConfig:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    return UniverseConfig.model_validate(raw)
