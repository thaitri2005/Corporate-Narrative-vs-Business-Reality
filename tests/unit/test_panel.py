from __future__ import annotations

from pathlib import Path

import polars as pl

from cnbr.analysis import build_thin_slice_panel
from cnbr.config import PanelBuildConfig


def test_panel_build_uses_true_next_fiscal_quarter(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pl.DataFrame(
        {
            "call_id": ["call-1"],
            "company_id": ["company-1"],
            "ticker": ["TEST"],
            "fiscal_year": [2023],
            "fiscal_quarter": [4],
            "eligible_word_count": [100],
        }
    ).write_parquet(data / "narrative.parquet")
    pl.DataFrame(
        {
            "company_id": ["company-1", "company-1"],
            "fiscal_year": [2023, 2024],
            "fiscal_quarter": [4, 1],
            "metric": ["revenue", "revenue_yoy"],
            "value": ["100", "0.2"],
        }
    ).write_parquet(data / "financial.parquet")
    config = PanelBuildConfig(
        narrative_path=Path("data/narrative.parquet"),
        financial_path=Path("data/financial.parquet"),
        output_path=Path("data/panel.parquet"),
        manifest_path=Path("reports/panel.json"),
        current_financial_metrics=["revenue"],
        lead_outcome_metrics=["revenue_yoy"],
    )

    result = build_thin_slice_panel(config, tmp_path)

    panel = pl.read_parquet(tmp_path / config.output_path).row(0, named=True)
    assert panel["current_revenue"] == "100"
    assert panel["lead1_fiscal_year"] == 2024
    assert panel["lead1_fiscal_quarter"] == 1
    assert panel["lead1_revenue_yoy"] == "0.2"
    assert result["observation_count"] == 1
