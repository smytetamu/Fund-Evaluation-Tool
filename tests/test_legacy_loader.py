"""Tests for legacy annual long-format ingestion."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from fund_evaluation_tool.ingestion.legacy_loader import (
    load_legacy_annual,
    normalise_legacy_for_metrics,
)

FIXTURE = Path(__file__).parent / "fixtures" / "legacy_annual_returns.csv"


# ── load_legacy_annual ────────────────────────────────────────────────────────

class TestLoadLegacyAnnual:
    def test_returns_three_objects(self):
        result = load_legacy_annual(FIXTURE)
        assert len(result) == 3

    def test_returns_wide_shape(self):
        returns_wide, _, _ = load_legacy_annual(FIXTURE)
        # Two funds × 6 years each
        assert returns_wide.shape == (6, 2)

    def test_returns_wide_columns(self):
        returns_wide, _, _ = load_legacy_annual(FIXTURE)
        assert set(returns_wide.columns) == {"HCI", "Global_Macro"}

    def test_index_is_datetime(self):
        returns_wide, _, _ = load_legacy_annual(FIXTURE)
        assert isinstance(returns_wide.index, pd.DatetimeIndex)

    def test_index_is_year_end(self):
        returns_wide, _, _ = load_legacy_annual(FIXTURE)
        # All dates should be Dec 31
        assert all(d.month == 12 and d.day == 31 for d in returns_wide.index)

    def test_known_return_value(self):
        returns_wide, _, _ = load_legacy_annual(FIXTURE)
        val = returns_wide.loc["2021-12-31", "HCI"]
        assert math.isclose(val, 0.223, rel_tol=1e-6)

    def test_benchmark_wide_has_spx_column(self):
        _, benchmark_wide, _ = load_legacy_annual(FIXTURE)
        assert "SPX" in benchmark_wide.columns

    def test_benchmark_spx_known_value(self):
        _, benchmark_wide, _ = load_legacy_annual(FIXTURE)
        val = benchmark_wide.loc["2019-12-31", "SPX"]
        assert math.isclose(val, 0.315, rel_tol=1e-6)

    def test_meta_has_partial_year_flag(self):
        _, _, meta = load_legacy_annual(FIXTURE)
        assert "Is_Partial_Year" in meta.columns

    def test_meta_partial_year_row(self):
        _, _, meta = load_legacy_annual(FIXTURE)
        partial = meta[(meta["Fund"] == "HCI") & (meta["Year"] == 2023)]
        assert partial["Is_Partial_Year"].iloc[0] == 1

    def test_meta_months_in_period(self):
        _, _, meta = load_legacy_annual(FIXTURE)
        partial = meta[(meta["Fund"] == "HCI") & (meta["Year"] == 2023)]
        assert partial["Months_In_Period"].iloc[0] == 9

    def test_raises_on_wrong_format(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("date,Fund_A,Fund_B\n2020-01-31,0.01,0.02\n")
        with pytest.raises(ValueError, match="legacy annual long format"):
            load_legacy_annual(bad_csv)


# ── normalise_legacy_for_metrics ──────────────────────────────────────────────

class TestNormaliseLegacyForMetrics:
    def test_includes_spx_column_by_default(self):
        df = normalise_legacy_for_metrics(FIXTURE)
        assert "SPX" in df.columns

    def test_excludes_spx_when_flag_false(self):
        df = normalise_legacy_for_metrics(FIXTURE, include_benchmark=False)
        assert "SPX" not in df.columns

    def test_fund_columns_present(self):
        df = normalise_legacy_for_metrics(FIXTURE)
        assert "HCI" in df.columns
        assert "Global_Macro" in df.columns

    def test_result_is_sorted_by_date(self):
        df = normalise_legacy_for_metrics(FIXTURE)
        assert list(df.index) == sorted(df.index)

    def test_no_duplicate_index(self):
        df = normalise_legacy_for_metrics(FIXTURE)
        assert df.index.is_unique

    def test_returns_are_decimal(self):
        """All values should be < 1 in absolute value for sane annual returns."""
        df = normalise_legacy_for_metrics(FIXTURE)
        assert (df.abs() < 2.0).all().all()

    def test_file_like_object(self):
        import io
        data = FIXTURE.read_bytes()
        df = normalise_legacy_for_metrics(io.BytesIO(data))
        assert "HCI" in df.columns
