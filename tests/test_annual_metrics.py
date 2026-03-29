"""Tests for annual-data metric calculations (annual_calculator.py)."""

import math
import warnings

import numpy as np
import pandas as pd
import pytest

from fund_evaluation_tool.metrics.annual_calculator import (
    compute_annual_metrics,
    compute_annual_metrics_with_benchmark,
    compute_annual_volatility,
    compute_arithmetic_mean,
    compute_cagr,
    compute_downside_deviation,
    compute_ending_value,
    compute_ips_compliance,
    compute_max_drawdown,
    compute_sharpe_annual,
    compute_sortino,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def annual(values, start_year=2010):
    """Build a pd.Series of annual returns with DatetimeIndex."""
    index = pd.date_range(
        start=f"{start_year}-12-31", periods=len(values), freq="YE"
    )
    return pd.Series(values, index=index)


def full_months(n, start_year=2010):
    """Parallel months_per_period with all full years (12)."""
    index = pd.date_range(
        start=f"{start_year}-12-31", periods=n, freq="YE"
    )
    return pd.Series([12] * n, index=index)


# ---------------------------------------------------------------------------
# compute_cagr
# ---------------------------------------------------------------------------

class TestComputeCagr:
    def test_full_years_simple(self):
        # 10% for 2 years → CAGR = 10%
        r = annual([0.10, 0.10])
        assert math.isclose(compute_cagr(r), 0.10, rel_tol=1e-9)

    def test_full_years_gross_compounding(self):
        # 50% then -33.33...% → gross = 1.0 → CAGR = 0%
        r = annual([0.5, -1 / 3])
        assert math.isclose(compute_cagr(r), 0.0, abs_tol=1e-9)

    def test_exact_fractional_year(self):
        # 6 months at 0% and 6 months at 0% → T=1, CAGR=0
        r = annual([0.0, 0.0])
        months = pd.Series([6, 6], index=r.index)
        assert math.isclose(compute_cagr(r, months), 0.0, abs_tol=1e-9)

    def test_partial_year_adjusts_T(self):
        # 10% for 6 months: T=0.5, CAGR = 1.10^(1/0.5) - 1 = 0.21
        r = annual([0.10])
        months = pd.Series([6], index=r.index)
        expected = 1.10 ** 2 - 1
        assert math.isclose(compute_cagr(r, months), expected, rel_tol=1e-9)

    def test_empty_series_returns_nan(self):
        assert math.isnan(compute_cagr(pd.Series([], dtype=float)))

    def test_negative_gross_returns_nan(self):
        r = annual([-1.5])  # gross = -0.5 — impossible but defensive
        assert math.isnan(compute_cagr(r))

    def test_nans_dropped(self):
        r = annual([float("nan"), 0.10])
        # Only one valid value of 0.10 → T=1 → CAGR = 10%
        assert math.isclose(compute_cagr(r), 0.10, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# compute_arithmetic_mean
# ---------------------------------------------------------------------------

class TestArithmeticMean:
    def test_simple_mean(self):
        r = annual([0.10, 0.20, 0.30])
        assert math.isclose(compute_arithmetic_mean(r), 0.20, rel_tol=1e-9)

    def test_empty_returns_nan(self):
        assert math.isnan(compute_arithmetic_mean(pd.Series([], dtype=float)))

    def test_single_value(self):
        r = annual([0.05])
        assert math.isclose(compute_arithmetic_mean(r), 0.05, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# compute_annual_volatility
# ---------------------------------------------------------------------------

class TestAnnualVolatility:
    def test_constant_series_is_zero(self):
        r = annual([0.10, 0.10, 0.10])
        assert math.isclose(compute_annual_volatility(r), 0.0, abs_tol=1e-12)

    def test_known_std(self):
        r = annual([0.0, 0.10])
        expected = float(pd.Series([0.0, 0.10]).std(ddof=1))
        assert math.isclose(compute_annual_volatility(r), expected, rel_tol=1e-9)

    def test_single_value_returns_nan(self):
        assert math.isnan(compute_annual_volatility(annual([0.10])))


# ---------------------------------------------------------------------------
# compute_downside_deviation
# ---------------------------------------------------------------------------

class TestDownsideDeviation:
    def test_no_shortfalls_returns_zero(self):
        r = annual([0.05, 0.10, 0.15])
        dd = compute_downside_deviation(r, mar=0.0)
        assert math.isclose(dd, 0.0, abs_tol=1e-12)

    def test_all_below_mar(self):
        r = annual([-0.10, -0.20])
        # shortfalls: [-0.10, -0.20], mean of squares = (0.01+0.04)/2=0.025
        expected = math.sqrt(0.025)
        assert math.isclose(compute_downside_deviation(r, mar=0.0), expected, rel_tol=1e-9)

    def test_mixed_shortfalls(self):
        r = annual([0.10, -0.10])
        # Only -0.10 contributes: mean of squares = 0.01/2 = 0.005
        expected = math.sqrt(0.005)
        assert math.isclose(compute_downside_deviation(r, mar=0.0), expected, rel_tol=1e-9)

    def test_mar_above_zero(self):
        r = annual([0.05, 0.15])
        # shortfalls vs MAR=0.10: [0.05-0.10, 0.15-0.10] = [-0.05, +0.05]
        # only -0.05 contributes: mean of squares = 0.0025/2 = 0.00125
        expected = math.sqrt(0.00125)
        assert math.isclose(compute_downside_deviation(r, mar=0.10), expected, rel_tol=1e-9)

    def test_empty_returns_nan(self):
        assert math.isnan(compute_downside_deviation(pd.Series([], dtype=float)))


# ---------------------------------------------------------------------------
# compute_sortino
# ---------------------------------------------------------------------------

class TestSortino:
    def test_basic(self):
        s = compute_sortino(cagr=0.10, downside_dev=0.05, risk_free_rate=0.0)
        assert math.isclose(s, 2.0, rel_tol=1e-9)

    def test_zero_downside_dev_returns_nan(self):
        assert math.isnan(compute_sortino(0.10, 0.0))

    def test_nan_cagr_returns_nan(self):
        assert math.isnan(compute_sortino(float("nan"), 0.05))

    def test_risk_free_rate_reduces_sortino(self):
        s1 = compute_sortino(0.10, 0.05, risk_free_rate=0.0)
        s2 = compute_sortino(0.10, 0.05, risk_free_rate=0.04)
        assert s1 > s2


# ---------------------------------------------------------------------------
# compute_ending_value
# ---------------------------------------------------------------------------

class TestEndingValue:
    def test_flat_positive(self):
        r = annual([0.10, 0.10])
        # 1M * 1.1 * 1.1 = 1,210,000
        assert math.isclose(compute_ending_value(r, 1_000_000), 1_210_000, rel_tol=1e-9)

    def test_empty_returns_nan(self):
        assert math.isnan(compute_ending_value(pd.Series([], dtype=float)))


# ---------------------------------------------------------------------------
# compute_max_drawdown
# ---------------------------------------------------------------------------

class TestMaxDrawdown:
    def test_no_drawdown(self):
        r = annual([0.10, 0.10, 0.10])
        assert math.isclose(compute_max_drawdown(r), 0.0, abs_tol=1e-12)

    def test_known_drawdown(self):
        # +50% then -50% → cumulative: 1.5 → 0.75 → drawdown = -0.5
        r = annual([0.5, -0.5])
        assert math.isclose(compute_max_drawdown(r), -0.5, rel_tol=1e-9)

    def test_empty_returns_nan(self):
        assert math.isnan(compute_max_drawdown(pd.Series([], dtype=float)))


# ---------------------------------------------------------------------------
# compute_sharpe_annual
# ---------------------------------------------------------------------------

class TestSharpeAnnual:
    def test_zero_vol_returns_nan(self):
        # Use 0.0 which is exactly representable → std = 0.0 exactly
        r = annual([0.0, 0.0, 0.0])
        assert math.isnan(compute_sharpe_annual(r))

    def test_positive_sharpe(self):
        r = annual([0.10, 0.12, 0.08])
        s = compute_sharpe_annual(r, risk_free_rate=0.0)
        assert s > 0

    def test_rf_reduces_sharpe(self):
        r = annual([0.10, 0.12, 0.08])
        s1 = compute_sharpe_annual(r, risk_free_rate=0.0)
        s2 = compute_sharpe_annual(r, risk_free_rate=0.05)
        assert s1 > s2


# ---------------------------------------------------------------------------
# compute_ips_compliance
# ---------------------------------------------------------------------------

class TestIpsCompliance:
    def test_compliant(self):
        result = compute_ips_compliance(cagr=0.10, cpi=0.03, target_spread=0.06)
        assert result["compliant"] is True
        assert math.isclose(result["ips_target"], 0.09, rel_tol=1e-9)
        assert math.isclose(result["delta"], 0.01, rel_tol=1e-9)

    def test_non_compliant(self):
        result = compute_ips_compliance(cagr=0.08, cpi=0.03, target_spread=0.06)
        assert result["compliant"] is False
        assert math.isclose(result["delta"], -0.01, rel_tol=1e-9)

    def test_exactly_at_target(self):
        result = compute_ips_compliance(cagr=0.09, cpi=0.03, target_spread=0.06)
        assert result["compliant"] is True
        assert math.isclose(result["delta"], 0.0, abs_tol=1e-12)

    def test_nan_cagr(self):
        result = compute_ips_compliance(float("nan"))
        assert result["compliant"] is False
        assert math.isnan(result["delta"])


# ---------------------------------------------------------------------------
# compute_annual_metrics (wrapper)
# ---------------------------------------------------------------------------

class TestComputeAnnualMetrics:
    def test_expected_keys(self):
        r = annual([0.10, 0.05, -0.03, 0.08])
        m = compute_annual_metrics(r)
        expected_keys = {
            "cagr", "arithmetic_mean_return", "annualised_volatility",
            "sharpe_ratio", "downside_deviation", "sortino_ratio",
            "max_drawdown", "calmar_ratio", "ending_value",
            "ips_target", "ips_compliant", "ips_delta",
            "num_periods", "total_years",
        }
        assert expected_keys == set(m.keys())

    def test_empty_returns_empty_dict(self):
        assert compute_annual_metrics(pd.Series([], dtype=float)) == {}

    def test_num_periods_correct(self):
        r = annual([0.10, 0.05, -0.03])
        m = compute_annual_metrics(r)
        assert m["num_periods"] == 3

    def test_total_years_with_partial(self):
        r = annual([0.10, 0.05])
        months = pd.Series([12, 6], index=r.index)
        m = compute_annual_metrics(r, months_per_period=months)
        assert math.isclose(m["total_years"], 1.5, rel_tol=1e-9)

    def test_total_years_full_default(self):
        r = annual([0.10, 0.05, 0.08])
        m = compute_annual_metrics(r)
        assert math.isclose(m["total_years"], 3.0, rel_tol=1e-9)

    def test_calmar_positive_when_drawdown_negative(self):
        r = annual([0.20, -0.10, 0.15])
        m = compute_annual_metrics(r)
        if not math.isnan(m["calmar_ratio"]):
            assert m["calmar_ratio"] > 0 or m["max_drawdown"] == 0


# ---------------------------------------------------------------------------
# compute_annual_metrics_with_benchmark
# ---------------------------------------------------------------------------

class TestBenchmarkMetrics:
    def _make_pair(self):
        fund = annual([0.12, 0.08, -0.05, 0.15])
        bench = annual([0.10, 0.06, -0.03, 0.12])
        return fund, bench

    def test_expected_keys_present(self):
        fund, bench = self._make_pair()
        m = compute_annual_metrics_with_benchmark(fund, bench)
        assert "cagr" in m
        assert "benchmark_cagr" in m
        assert "excess_cagr" in m

    def test_excess_cagr_calculation(self):
        fund, bench = self._make_pair()
        m = compute_annual_metrics_with_benchmark(fund, bench)
        assert math.isclose(
            m["excess_cagr"], m["cagr"] - m["benchmark_cagr"], rel_tol=1e-9
        )

    def test_partial_overlap_emits_warning(self):
        fund = annual([0.10, 0.05, 0.08, 0.12], start_year=2010)
        # Benchmark only covers 2011–2013
        bench = annual([0.09, 0.04, 0.11], start_year=2011)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            m = compute_annual_metrics_with_benchmark(fund, bench)
            assert len(w) == 1
            assert "dropped" in str(w[0].message).lower()

    def test_no_overlap_returns_empty(self):
        fund = annual([0.10], start_year=2010)
        bench = annual([0.10], start_year=2020)
        m = compute_annual_metrics_with_benchmark(fund, bench)
        assert m == {}

    def test_benchmark_metrics_prefixed(self):
        fund, bench = self._make_pair()
        m = compute_annual_metrics_with_benchmark(fund, bench)
        for key in ["cagr", "annualised_volatility", "sharpe_ratio", "sortino_ratio"]:
            assert f"benchmark_{key}" in m
