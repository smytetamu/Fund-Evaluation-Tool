"""Tests for benchmark comparison calculations."""

import math
import pandas as pd
import pytest

from fund_evaluation_tool.benchmark.comparison import compute_benchmark_comparison


def make_df(n: int = 24) -> pd.DataFrame:
    """Returns a simple DataFrame with two funds and a benchmark."""
    return pd.DataFrame({
        "FundA": [0.01] * n,
        "FundB": [0.02] * n,
        "Benchmark": [0.005] * n,
    })


def test_output_contains_expected_columns():
    df = make_df()
    result = compute_benchmark_comparison(df, "Benchmark")
    expected = {
        "fund_ann_return", "benchmark_ann_return", "excess_return",
        "tracking_error", "information_ratio", "beta", "alpha", "correlation",
    }
    assert expected == set(result.columns)


def test_funds_in_index_exclude_benchmark():
    df = make_df()
    result = compute_benchmark_comparison(df, "Benchmark")
    assert "Benchmark" not in result.index
    assert "FundA" in result.index
    assert "FundB" in result.index


def test_excess_return_sign():
    """FundB (2%/mo) should have higher excess return than FundA (1%/mo)."""
    df = make_df()
    result = compute_benchmark_comparison(df, "Benchmark")
    assert result.loc["FundB", "excess_return"] > result.loc["FundA", "excess_return"]


def test_excess_return_positive_for_outperformer():
    df = make_df()
    result = compute_benchmark_comparison(df, "Benchmark")
    # Both 1% and 2%/mo outperform 0.5%/mo benchmark
    assert result.loc["FundA", "excess_return"] > 0
    assert result.loc["FundB", "excess_return"] > 0


def test_tracking_error_zero_for_identical_returns():
    """Fund with identical returns to benchmark → zero tracking error."""
    df = pd.DataFrame({
        "FundSame": [0.005] * 24,
        "Benchmark": [0.005] * 24,
    })
    result = compute_benchmark_comparison(df, "Benchmark")
    assert math.isclose(result.loc["FundSame", "tracking_error"], 0.0, abs_tol=1e-10)


def test_information_ratio_nan_for_zero_tracking_error():
    """Zero tracking error → IR should be NaN (not div-by-zero error)."""
    df = pd.DataFrame({
        "FundSame": [0.005] * 24,
        "Benchmark": [0.005] * 24,
    })
    result = compute_benchmark_comparison(df, "Benchmark")
    assert math.isnan(result.loc["FundSame", "information_ratio"])


def test_benchmark_ann_return_same_for_all_funds():
    """benchmark_ann_return should be the same value for every row."""
    df = make_df()
    result = compute_benchmark_comparison(df, "Benchmark")
    values = result["benchmark_ann_return"].dropna().unique()
    assert len(values) == 1


def test_empty_fund_returns_nan_row():
    """Fund column of all NaN should produce NaN metrics without crashing."""
    df = pd.DataFrame({
        "FundNaN": [float("nan")] * 12,
        "Benchmark": [0.005] * 12,
    })
    result = compute_benchmark_comparison(df, "Benchmark")
    assert math.isnan(result.loc["FundNaN", "excess_return"])


def test_single_fund_only():
    """Single fund besides benchmark should work fine."""
    df = pd.DataFrame({
        "FundA": [0.01] * 12,
        "Benchmark": [0.005] * 12,
    })
    result = compute_benchmark_comparison(df, "Benchmark")
    assert len(result) == 1
    assert "FundA" in result.index
