"""Data ingestion: load and parse fund data from CSV/Excel sources."""

from .loader import load_fund_data

__all__ = ["load_fund_data"]
