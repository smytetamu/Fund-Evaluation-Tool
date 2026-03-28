"""Tests for core metric calculations."""

import math
import pandas as pd
import pytest

from fund_evaluation_tool.metrics.calculator import compute_metrics


# ── helpers ──────────────────────────────────────────────────────────────────

def flat_series(monthly_return: float, n: int = 24) -> pd.Series:
    return pd.Series([monthly_return] * n)


# ── basic contract ────────────────────────────────────────────────────────────

def test_returns_expected_keys():
    m = compute_metrics(flat_series(0.01))
    expected = {"total_return", "annualised_return", "annualised_volatility",
                "sharpe_ratio", "max_drawdown", "calmar_ratio", "num_periods"}
    assert expected == set(m.keys())


def test_empty_series_returns_empty_dict():
    assert compute_metrics(pd.Series([], dtype=float)) == {}


def test_series_with_all_nans_returns_empty_dict():
    assert compute_metrics(pd.Series([float("nan"), float("nan")])) == {}


# ── total return ──────────────────────────────────────────────────────────────

def test_total_return_positive_flat():
    m = compute_metrics(flat_series(0.01, n=12))
    # (1.01)^12 - 1
    expected = (1.01 ** 12) - 1
    assert math.isclose(m["total_return"], expected, rel_tol=1e-9)


def test_total_return_all_zeros():
    m = compute_metrics(flat_series(0.0, n=12))
    assert math.isclose(m["total_return"], 0.0, abs_tol=1e-12)


# ── annualised return ─────────────────────────────────────────────────────────

def test_annualised_return_exact_one_year():
    """12 months of identical returns → annualised equals total."""
    m = compute_metrics(flat_series(0.01, n=12))
    assert math.isclose(m["annualised_return"], m["total_return"], rel_tol=1e-9)


def test_annualised_return_two_years():
    """24 months of 1% → annualised ≈ (1.01^24)^(12/24) - 1 = 1.01^12 - 1."""
    m = compute_metrics(flat_series(0.01, n=24))
    expected = (1.01 ** 12) - 1
    assert math.isclose(m["annualised_return"], expected, rel_tol=1e-9)


# ── volatility ────────────────────────────────────────────────────────────────

def test_volatility_zero_for_constant_returns():
    m = compute_metrics(flat_series(0.01, n=24))
    assert math.isclose(m["annualised_volatility"], 0.0, abs_tol=1e-12)


def test_volatility_positive_for_mixed_returns():
    returns = pd.Series([0.05, -0.03, 0.02, -0.01, 0.04])
    m = compute_metrics(returns)
    assert m["annualised_volatility"] > 0


# ── sharpe ratio ──────────────────────────────────────────────────────────────

def test_sharpe_is_nan_for_zero_volatility():
    # Flat returns → zero vol → NaN sharpe
    m = compute_metrics(flat_series(0.01, n=24))
    assert math.isnan(m["sharpe_ratio"])


def test_sharpe_higher_with_lower_risk_free():
    returns = pd.Series([0.02, 0.03, -0.01, 0.04, 0.01] * 4)
    m_low_rf = compute_metrics(returns, risk_free_rate=0.0)
    m_high_rf = compute_metrics(returns, risk_free_rate=0.05)
    assert m_low_rf["sharpe_ratio"] > m_high_rf["sharpe_ratio"]


# ── max drawdown ──────────────────────────────────────────────────────────────

def test_max_drawdown_non_positive():
    returns = pd.Series([0.05, -0.10, 0.03, -0.02, 0.08])
    m = compute_metrics(returns)
    assert m["max_drawdown"] <= 0


def test_max_drawdown_zero_for_monotone_gains():
    m = compute_metrics(flat_series(0.01, n=12))
    assert math.isclose(m["max_drawdown"], 0.0, abs_tol=1e-12)


def test_max_drawdown_known_value():
    # One period: +50%, then -50% → cumulative: 1.5 → 0.75 → drawdown = -0.5
    returns = pd.Series([0.5, -0.5])
    m = compute_metrics(returns)
    assert math.isclose(m["max_drawdown"], -0.5, rel_tol=1e-9)


# ── num_periods ───────────────────────────────────────────────────────────────

def test_num_periods_correct():
    m = compute_metrics(flat_series(0.01, n=36))
    assert m["num_periods"] == 36


def test_num_periods_ignores_nans():
    s = pd.Series([0.01, float("nan"), 0.02, 0.03])
    m = compute_metrics(s)
    assert m["num_periods"] == 3
