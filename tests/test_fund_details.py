"""Tests for FundDetails and AnchorWindow."""

import pandas as pd
import pytest

from fund_evaluation_tool.fund_details import AnchorWindow, FundDetails, FundDetailsConfig


# ---------------------------------------------------------------------------
# FundDetails
# ---------------------------------------------------------------------------


class TestFundDetails:
    def test_defaults(self):
        d = FundDetails(name="FundA")
        assert d.include is True
        assert d.return_type == "Gross"
        assert d.high_water_mark is False
        assert d.liquidity_notes == ""

    def test_to_dict_contains_name(self):
        d = FundDetails(name="FundB", include=False)
        result = d.to_dict()
        assert result["name"] == "FundB"
        assert result["include"] is False


# ---------------------------------------------------------------------------
# FundDetailsConfig
# ---------------------------------------------------------------------------


class TestFundDetailsConfig:
    def test_get_creates_default(self):
        cfg = FundDetailsConfig()
        d = cfg.get("FundA")
        assert d.name == "FundA"
        assert d.include is True

    def test_get_returns_same_instance(self):
        cfg = FundDetailsConfig()
        d1 = cfg.get("FundA")
        d2 = cfg.get("FundA")
        assert d1 is d2

    def test_set_and_get(self):
        cfg = FundDetailsConfig()
        d = FundDetails(name="FundA", include=False)
        cfg.set(d)
        assert cfg.get("FundA").include is False

    def test_included_funds(self):
        cfg = FundDetailsConfig()
        cfg.set(FundDetails(name="A", include=True))
        cfg.set(FundDetails(name="B", include=False))
        cfg.set(FundDetails(name="C", include=True))
        assert set(cfg.included_funds()) == {"A", "C"}

    def test_sync_removes_stale(self):
        cfg = FundDetailsConfig()
        cfg.get("A")
        cfg.get("B")
        cfg.sync_from_names(["A"])
        assert cfg.included_funds() == ["A"]

    def test_sync_adds_missing(self):
        cfg = FundDetailsConfig()
        cfg.sync_from_names(["A", "B"])
        assert set(cfg.included_funds()) == {"A", "B"}


# ---------------------------------------------------------------------------
# AnchorWindow
# ---------------------------------------------------------------------------


def _make_returns_wide() -> pd.DataFrame:
    """Returns wide frame with two funds spanning different date ranges."""
    idx = pd.date_range("2000-12-31", periods=5, freq="YE")
    df = pd.DataFrame(
        {
            "FundA": [0.10, 0.08, 0.12, 0.05, 0.09],
            "FundB": [float("nan"), 0.07, 0.11, 0.04, 0.08],
        },
        index=idx,
    )
    return df


class TestAnchorWindow:
    def test_effective_start_year_no_anchor(self):
        aw = AnchorWindow()
        assert aw.effective_start_year is None

    def test_effective_start_year_uses_anchor(self):
        aw = AnchorWindow(anchor_start_year=2005)
        assert aw.effective_start_year == 2005

    def test_effective_start_year_override_takes_precedence(self):
        aw = AnchorWindow(anchor_start_year=2000, override_start_year=2005)
        assert aw.effective_start_year == 2005

    def test_resolve_anchor_sets_first_year(self):
        df = _make_returns_wide()
        aw = AnchorWindow(anchor_fund="FundA")
        aw.resolve_anchor(df)
        assert aw.anchor_start_year == 2000

    def test_resolve_anchor_skips_nans(self):
        """FundB starts with NaN — anchor year should be the first non-NaN row."""
        df = _make_returns_wide()
        aw = AnchorWindow(anchor_fund="FundB")
        aw.resolve_anchor(df)
        # FundB has NaN in 2000, first valid is 2001
        assert aw.anchor_start_year == 2001

    def test_resolve_anchor_unknown_fund(self):
        df = _make_returns_wide()
        aw = AnchorWindow(anchor_fund="FundX")
        aw.resolve_anchor(df)
        assert aw.anchor_start_year is None

    def test_clip_to_window_no_effective_year(self):
        df = _make_returns_wide()
        aw = AnchorWindow()
        result = aw.clip_to_window(df)
        assert len(result) == len(df)

    def test_clip_to_window_clips_rows(self):
        df = _make_returns_wide()
        aw = AnchorWindow(anchor_start_year=2002)
        result = aw.clip_to_window(df)
        assert result.index.min().year >= 2002
        assert len(result) < len(df)

    def test_clip_to_window_with_override(self):
        df = _make_returns_wide()
        aw = AnchorWindow(anchor_start_year=2000, override_start_year=2003)
        result = aw.clip_to_window(df)
        assert result.index.min().year >= 2003


# ---------------------------------------------------------------------------
# app_logic integration — defaults
# ---------------------------------------------------------------------------


def test_default_risk_free_is_workbook_value():
    from fund_evaluation_tool.app_logic import DEFAULT_RISK_FREE
    assert DEFAULT_RISK_FREE == 0.02


def test_default_cpi_is_workbook_value():
    from fund_evaluation_tool.app_logic import DEFAULT_CPI
    assert DEFAULT_CPI == 0.03


def test_default_ips_spread_is_workbook_value():
    from fund_evaluation_tool.app_logic import DEFAULT_IPS_SPREAD
    assert DEFAULT_IPS_SPREAD == 0.06
