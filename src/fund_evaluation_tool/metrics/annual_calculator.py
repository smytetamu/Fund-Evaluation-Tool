"""Annual-data metric calculations for the legacy fund evaluation path.

This module complements ``calculator.py`` (which assumes monthly data) with
functions designed for annual return series, including:
- CAGR with partial-year handling
- Arithmetic average return
- Annualised volatility from annual returns
- Downside deviation
- Sortino ratio
- Ending value
- IPS compliance flag
- A convenience wrapper that computes all metrics for a fund series and
  (optionally) a benchmark series side-by-side.

All open-question defaults are documented inline with ``# ASSUMPTION:`` tags.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------


def compute_cagr(
    annual_returns: pd.Series,
    months_per_period: pd.Series | None = None,
) -> float:
    """Compute CAGR with optional partial-year handling.

    Parameters
    ----------
    annual_returns:
        Series of decimal annual returns (e.g. 0.12 for 12%).
    months_per_period:
        Parallel Series of integers (1–12) representing the number of months
        in each period.  Full-year rows should be 12.  If None, every period
        is assumed to be a full year (T = len(annual_returns)).

    Returns
    -------
    float — CAGR (annualised compound return).  NaN if T == 0 or gross <= 0.
    """
    annual_returns = annual_returns.dropna()
    if annual_returns.empty:
        return float("nan")

    if months_per_period is not None:
        months_per_period = months_per_period.reindex(annual_returns.index)
        months_per_period = months_per_period.fillna(12)
        T = float(months_per_period.sum()) / 12.0
    else:
        T = float(len(annual_returns))

    if T == 0:
        return float("nan")

    gross = float((1 + annual_returns).prod())
    if gross <= 0:
        return float("nan")

    return float(gross ** (1.0 / T) - 1)


def compute_arithmetic_mean(annual_returns: pd.Series) -> float:
    """Simple arithmetic mean of annual returns.

    ASSUMPTION: Partial-year rows are included as-is (not excluded or
    pro-rated).  This matches the most common legacy workbook convention.
    """
    annual_returns = annual_returns.dropna()
    if annual_returns.empty:
        return float("nan")
    return float(annual_returns.mean())


def compute_annual_volatility(annual_returns: pd.Series) -> float:
    """Annualised volatility from an annual return series.

    For annual data, no sqrt(12) scaling is applied — std of annual returns
    is already an annual volatility.  Uses sample std (ddof=1).
    """
    annual_returns = annual_returns.dropna()
    if len(annual_returns) < 2:
        return float("nan")
    return float(annual_returns.std(ddof=1))


def compute_downside_deviation(
    annual_returns: pd.Series,
    mar: float = 0.0,
) -> float:
    """Compute downside deviation (semi-deviation below MAR).

    Uses the **population** formula (divide by N), consistent with standard
    Sortino ratio convention.

    Parameters
    ----------
    annual_returns:
        Series of decimal annual returns.
    mar:
        Minimum acceptable return (default 0.0).
        ASSUMPTION: MAR = 0.0 (no hurdle); change once workbook Inputs
        sheet has been inspected.

    Returns
    -------
    float — downside deviation.  NaN if series is empty.
    """
    annual_returns = annual_returns.dropna()
    if annual_returns.empty:
        return float("nan")

    shortfalls = np.minimum(annual_returns - mar, 0.0)
    return float(np.sqrt(np.mean(shortfalls ** 2)))


def compute_sortino(
    cagr: float,
    downside_dev: float,
    risk_free_rate: float = 0.0,
) -> float:
    """Compute Sortino ratio.

    Parameters
    ----------
    cagr:
        Annualised compound return (from ``compute_cagr``).
    downside_dev:
        Downside deviation (from ``compute_downside_deviation``).
    risk_free_rate:
        Annualised risk-free rate.  Default 0.0.
        ASSUMPTION: 0.0 pending workbook Inputs confirmation.

    Returns
    -------
    float — Sortino ratio.  NaN if downside_dev == 0 or inputs are NaN.
    """
    if math.isnan(cagr) or math.isnan(downside_dev):
        return float("nan")
    if downside_dev == 0.0:
        return float("nan")
    return float((cagr - risk_free_rate) / downside_dev)


def compute_ending_value(
    annual_returns: pd.Series,
    starting_value: float = 1_000_000.0,
) -> float:
    """Compute ending portfolio value.

    Parameters
    ----------
    annual_returns:
        Series of decimal annual returns.
    starting_value:
        Initial portfolio value.  Default $1,000,000.

    Returns
    -------
    float — ending value.
    """
    annual_returns = annual_returns.dropna()
    if annual_returns.empty:
        return float("nan")
    gross = float((1 + annual_returns).prod())
    return float(starting_value * gross)


def compute_max_drawdown(annual_returns: pd.Series) -> float:
    """Maximum drawdown from an annual return series.

    Returns a non-positive float (0.0 = no drawdown, -0.5 = 50% drawdown).
    Returns NaN if series is empty.
    """
    annual_returns = annual_returns.dropna()
    if annual_returns.empty:
        return float("nan")
    cumulative = (1 + annual_returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    return float(drawdown.min())


def compute_sharpe_annual(
    annual_returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> float:
    """Sharpe ratio from annual returns using arithmetic mean.

    ASSUMPTION: Legacy workbook uses arithmetic mean (not CAGR) in the Sharpe
    numerator for annual-data series.  Pending workbook confirmation.

    Parameters
    ----------
    annual_returns:
        Series of decimal annual returns.
    risk_free_rate:
        Annualised risk-free rate.  Default 0.0.

    Returns
    -------
    float — Sharpe ratio.  NaN if volatility == 0.
    """
    mean_ret = compute_arithmetic_mean(annual_returns)
    vol = compute_annual_volatility(annual_returns)
    if math.isnan(mean_ret) or math.isnan(vol) or vol == 0.0:
        return float("nan")
    return float((mean_ret - risk_free_rate) / vol)


def compute_ips_compliance(
    cagr: float,
    cpi: float = 0.03,
    target_spread: float = 0.06,
) -> dict:
    """Evaluate IPS compliance: CAGR >= CPI + target_spread.

    Parameters
    ----------
    cagr:
        Annualised CAGR of the fund (gross, until fee engine is available).
    cpi:
        CPI assumption.  Default 3.0% (0.03).
        ASSUMPTION: 3.0% pending workbook Inputs sheet confirmation.
    target_spread:
        Target excess return over CPI.  Default 6.0% (0.06), per parity memo.

    Returns
    -------
    dict with keys: ips_target (float), compliant (bool), delta (float).
    NaN cagr → compliant=False, delta=NaN.
    """
    ips_target = cpi + target_spread
    if math.isnan(cagr):
        return {"ips_target": ips_target, "compliant": False, "delta": float("nan")}
    delta = cagr - ips_target
    return {
        "ips_target": ips_target,
        "compliant": bool(cagr >= ips_target),
        "delta": float(delta),
    }


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def compute_annual_metrics(
    annual_returns: pd.Series,
    months_per_period: pd.Series | None = None,
    risk_free_rate: float = 0.0,
    mar: float = 0.0,
    starting_value: float = 1_000_000.0,
    cpi: float = 0.03,
    ips_target_spread: float = 0.06,
) -> dict:
    """Compute full suite of annual-data metrics for a single return series.

    Parameters
    ----------
    annual_returns:
        Series of decimal annual returns.
    months_per_period:
        Optional parallel Series (1–12) for partial-year CAGR calculation.
    risk_free_rate:
        Annualised risk-free rate.  Default 0.0.
    mar:
        Minimum acceptable return for downside deviation.  Default 0.0.
    starting_value:
        Portfolio starting value for ending-value calculation.  Default $1M.
    cpi:
        CPI assumption for IPS compliance.  Default 3.0%.
    ips_target_spread:
        IPS target spread above CPI.  Default 6.0%.

    Returns
    -------
    dict of metric name → value.
    """
    annual_returns = annual_returns.dropna()
    if annual_returns.empty:
        return {}

    cagr = compute_cagr(annual_returns, months_per_period)
    arith_mean = compute_arithmetic_mean(annual_returns)
    vol = compute_annual_volatility(annual_returns)
    sharpe = compute_sharpe_annual(annual_returns, risk_free_rate)
    dd = compute_downside_deviation(annual_returns, mar)
    sortino = compute_sortino(cagr, dd, risk_free_rate)
    max_dd = compute_max_drawdown(annual_returns)
    calmar = float(cagr / abs(max_dd)) if (not math.isnan(cagr) and max_dd < 0) else float("nan")
    ending_val = compute_ending_value(annual_returns, starting_value)
    ips = compute_ips_compliance(cagr, cpi, ips_target_spread)
    num_periods = len(annual_returns)
    total_years = (
        float(months_per_period.reindex(annual_returns.index).fillna(12).sum()) / 12.0
        if months_per_period is not None
        else float(num_periods)
    )

    return {
        "cagr": cagr,
        "arithmetic_mean_return": arith_mean,
        "annualised_volatility": vol,
        "sharpe_ratio": sharpe,
        "downside_deviation": dd,
        "sortino_ratio": sortino,
        "max_drawdown": max_dd,
        "calmar_ratio": calmar,
        "ending_value": ending_val,
        "ips_target": ips["ips_target"],
        "ips_compliant": ips["compliant"],
        "ips_delta": ips["delta"],
        "num_periods": num_periods,
        "total_years": total_years,
    }


def compute_annual_metrics_with_benchmark(
    fund_returns: pd.Series,
    benchmark_returns: pd.Series,
    months_per_period: pd.Series | None = None,
    risk_free_rate: float = 0.0,
    mar: float = 0.0,
    starting_value: float = 1_000_000.0,
    cpi: float = 0.03,
    ips_target_spread: float = 0.06,
) -> dict:
    """Compute metrics for fund and benchmark over identical aligned date range.

    Fund and benchmark rows are aligned; any year missing from either series
    is dropped from both before computing metrics.  A warning is emitted if
    rows are dropped.

    Parameters
    ----------
    fund_returns, benchmark_returns:
        Annual return series (may have different or overlapping DatetimeIndex).
    months_per_period:
        Optional months-in-period Series indexed consistently with fund_returns.
    Other parameters:
        Passed through to ``compute_annual_metrics``.

    Returns
    -------
    dict with all fund metric keys plus benchmark_ prefixed equivalents and
    excess_cagr.
    """
    # Align on shared index
    aligned = pd.concat(
        {"fund": fund_returns, "benchmark": benchmark_returns}, axis=1
    ).dropna()

    dropped = len(fund_returns.dropna()) + len(benchmark_returns.dropna()) - 2 * len(aligned)
    if dropped > 0:
        warnings.warn(
            f"{dropped} row(s) dropped to align fund and benchmark date ranges.",
            stacklevel=2,
        )

    if aligned.empty:
        return {}

    fund_aligned = aligned["fund"]
    bench_aligned = aligned["benchmark"]

    # Align months_per_period to the common index
    if months_per_period is not None:
        months_aligned = months_per_period.reindex(aligned.index)
    else:
        months_aligned = None

    fund_metrics = compute_annual_metrics(
        fund_aligned,
        months_per_period=months_aligned,
        risk_free_rate=risk_free_rate,
        mar=mar,
        starting_value=starting_value,
        cpi=cpi,
        ips_target_spread=ips_target_spread,
    )

    bench_metrics = compute_annual_metrics(
        bench_aligned,
        months_per_period=months_aligned,
        risk_free_rate=risk_free_rate,
        mar=mar,
        starting_value=starting_value,
        cpi=cpi,
        ips_target_spread=ips_target_spread,
    )

    result = dict(fund_metrics)
    for k, v in bench_metrics.items():
        result[f"benchmark_{k}"] = v

    # Derived: excess CAGR
    fund_cagr = fund_metrics.get("cagr", float("nan"))
    bench_cagr = bench_metrics.get("cagr", float("nan"))
    result["excess_cagr"] = (
        float(fund_cagr - bench_cagr)
        if not (math.isnan(fund_cagr) or math.isnan(bench_cagr))
        else float("nan")
    )

    return result
