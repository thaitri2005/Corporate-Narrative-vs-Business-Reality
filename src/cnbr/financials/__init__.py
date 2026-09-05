"""SEC financial-fact normalization and feasibility analysis."""

from cnbr.financials.alignment import build_fiscal_alignment
from cnbr.financials.coverage import build_concept_coverage
from cnbr.financials.filing_index import build_filing_index

__all__ = ["build_concept_coverage", "build_filing_index", "build_fiscal_alignment"]
