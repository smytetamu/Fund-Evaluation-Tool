"""Pure helpers for wiring data shapes into the Streamlit UI."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Literal

import pandas as pd

from fund_evaluation_tool.benchmark import compute_benchmark_comparison
from fund_evaluation_tool.ingestion.legacy_loader import load_legacy_annual
from fund_evaluation_tool.metrics.annual_calculator import (
    compute_annual_metrics,
    compute_annual_metrics_with_benchmark,
)

LegacyFormat = Literal["legacy_annual", "monthly_wide"]


_REQUIRED_LEGACY_COLS = {"Fund", "Year", "Fund_Return"}


def _build_legacy_assumptions_summary(
    *,
    risk_free_rate: float,
    has_partial_years: bool,
    has_spx: bool,
) -> tuple[dict[str, Any], pd.DataFrame]:
    assumptions = {
        "cpi": 0.03,
        "risk_free_rate": risk_free_rate,
        "mar": 0.0,
        "ips_target_spread": 0.06,
    }
    summary = pd.DataFrame(
        [
            {
                "Assumption": "CPI assumption",
                "Value": assumptions["cpi"],
                "Status": "Placeholder",
                "Source": "Parity memo; workbook Inputs sheet not yet confirmed",
            },
            {
                "Assumption": "IPS target spread",
                "Value": assumptions["ips_target_spread"],
                "Status": "Documented",
                "Source": "Parity memo target is CPI + 6%",
            },
            {
                "Assumption": "Risk-free rate",
                "Value": assumptions["risk_free_rate"],
                "Status": "User setting",
                "Source": "Streamlit sidebar input applied to annual Sharpe/Sortino",
            },
            {
                "Assumption": "MAR",
                "Value": assumptions["mar"],
                "Status": "Default",
                "Source": "Downside deviation / Sortino currently use MAR = 0.0",
            },
            {
                "Assumption": "Partial-year handling",
                "Value": "Included using Months_In_Period"
                if has_partial_years
                else "Full-year rows only in sample",
                "Status": "Implemented",
                "Source": "CAGR total years = sum(Months_In_Period / 12)",
            },
            {
                "Assumption": "Benchmark source",
                "Value": "SPX_Return column" if has_spx else "No benchmark column supplied",
                "Status": "Input-derived",
                "Source": "Legacy upload provides annual SPX rows when present",
            },
            {
                "Assumption": "Fee treatment",
                "Value": "Gross / pre-fee returns",
                "Status": "Placeholder",
                "Source": "Fee engine not implemented in MVP",
            },
        ]
    )
    return assumptions, summary


def read_uploaded_frame(source: str | Path | IO) -> pd.DataFrame:
    """Read an uploaded CSV/Excel file without applying shape-specific transforms."""
    if isinstance(source, (str, Path)):
        name = Path(source).name
    else:
        name = getattr(source, "name", "data.csv")

    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(source)
    return pd.read_csv(source)


def detect_input_format(columns: list[str] | pd.Index) -> LegacyFormat:
    """Detect whether uploaded data looks like the legacy annual long format."""
    if _REQUIRED_LEGACY_COLS.issubset(set(columns)):
        return "legacy_annual"
    return "monthly_wide"


def build_legacy_analysis(
    source: str | Path | IO,
    risk_free_rate: float = 0.0,
) -> dict[str, Any]:
    """Compute legacy annual metrics and optional SPX comparison for the UI."""
    returns_wide, benchmark_wide, meta = load_legacy_annual(source)

    benchmark_series = benchmark_wide["SPX"] if "SPX" in benchmark_wide.columns else None
    raw_data_df = meta.copy()
    raw_data_df["Fund_Return"] = [
        returns_wide.loc[pd.Timestamp(f"{int(year)}-12-31"), fund]
        for fund, year in zip(meta["Fund"], meta["Year"], strict=False)
    ]
    if benchmark_series is not None:
        raw_data_df["SPX_Return"] = [
            benchmark_series.loc[pd.Timestamp(f"{int(year)}-12-31")]
            for year in meta["Year"]
        ]
    all_metrics: dict[str, dict[str, Any]] = {}
    comparison_rows: dict[str, dict[str, Any]] = {}
    has_partial_years = bool(meta.get("Is_Partial_Year", pd.Series(dtype=int)).fillna(0).astype(int).eq(1).any())

    for fund in returns_wide.columns:
        series = returns_wide[fund].dropna()
        fund_meta = meta.loc[meta["Fund"] == fund].copy()
        months_per_period = None
        if not fund_meta.empty and "Months_In_Period" in fund_meta.columns:
            months_per_period = pd.Series(
                fund_meta["Months_In_Period"].fillna(12).to_list(),
                index=pd.to_datetime(fund_meta["Year"].astype(int).astype(str) + "-12-31"),
            ).sort_index()

        metrics = compute_annual_metrics(
            series,
            months_per_period=months_per_period,
            risk_free_rate=risk_free_rate,
        )
        all_metrics[fund] = metrics

        if benchmark_series is not None:
            comparison = compute_annual_metrics_with_benchmark(
                series,
                benchmark_series,
                months_per_period=months_per_period,
                risk_free_rate=risk_free_rate,
            )
            comparison_rows[fund] = {
                "fund_cagr": comparison.get("cagr"),
                "benchmark_cagr": comparison.get("benchmark_cagr"),
                "excess_cagr": comparison.get("excess_cagr"),
                "fund_ips_compliant": comparison.get("ips_compliant"),
                "benchmark_ips_compliant": comparison.get("benchmark_ips_compliant"),
                "fund_total_years": comparison.get("total_years"),
            }

    assumptions, assumptions_df = _build_legacy_assumptions_summary(
        risk_free_rate=risk_free_rate,
        has_partial_years=has_partial_years,
        has_spx=benchmark_series is not None,
    )

    return {
        "returns_df": returns_wide.join(benchmark_wide, how="left") if not benchmark_wide.empty else returns_wide,
        "raw_data_df": raw_data_df,
        "all_metrics": all_metrics,
        "benchmark_comparison_df": pd.DataFrame(comparison_rows).T if comparison_rows else None,
        "assumptions": assumptions,
        "assumptions_df": assumptions_df,
        "has_spx": benchmark_series is not None,
        "fund_count": len(returns_wide.columns),
        "row_count": len(returns_wide),
    }


def build_monthly_benchmark_analysis(
    returns_df: pd.DataFrame,
    benchmark_col: str,
) -> pd.DataFrame:
    return compute_benchmark_comparison(returns_df, benchmark_col)
