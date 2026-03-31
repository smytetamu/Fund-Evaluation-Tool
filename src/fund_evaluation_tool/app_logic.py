"""Pure helpers for wiring data shapes into the Streamlit UI."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Literal

import pandas as pd

from fund_evaluation_tool.benchmark import compute_benchmark_comparison
from fund_evaluation_tool.fund_details import AnchorWindow
from fund_evaluation_tool.ingestion.legacy_loader import load_legacy_annual
from fund_evaluation_tool.metrics.annual_calculator import (
    compute_annual_metrics,
    compute_annual_metrics_with_benchmark,
)

LegacyFormat = Literal["legacy_annual", "monthly_wide"]


_REQUIRED_LEGACY_COLS = {"Fund", "Year", "Fund_Return"}

# Workbook-confirmed defaults (from direct inspection of IPS_MultiFund_Model_v13.2.xlsm)
DEFAULT_RISK_FREE = 0.02
DEFAULT_CPI = 0.03
DEFAULT_IPS_SPREAD = 0.06


def _build_legacy_assumptions_summary(
    *,
    risk_free_rate: float,
    has_partial_years: bool,
    benchmark_name: str | None,
    anchor_window: AnchorWindow | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    assumptions = {
        "cpi": DEFAULT_CPI,
        "risk_free_rate": risk_free_rate,
        "mar": 0.0,
        "ips_target_spread": DEFAULT_IPS_SPREAD,
    }
    rows = [
        {
            "Assumption": "CPI assumption",
            "Value": assumptions["cpi"],
            "Status": "Confirmed",
            "Source": "Direct inspection of workbook Inputs sheet (v13.2)",
        },
        {
            "Assumption": "IPS target spread",
            "Value": assumptions["ips_target_spread"],
            "Status": "Confirmed",
            "Source": "Workbook Inputs: IPS target premium = 6.0%",
        },
        {
            "Assumption": "Risk-free rate",
            "Value": assumptions["risk_free_rate"],
            "Status": "Workbook default / user override",
            "Source": "Workbook Inputs default = 2.0%; user can override in sidebar",
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
            "Value": benchmark_name if benchmark_name else "No benchmark selected",
            "Status": "User-selected",
            "Source": "Selected from loaded fund columns; not limited to SPX_Return",
        },
        {
            "Assumption": "Fee treatment",
            "Value": "Gross / pre-fee returns",
            "Status": "Placeholder",
            "Source": "Fee engine not implemented in MVP",
        },
    ]
    if anchor_window is not None and anchor_window.effective_start_year is not None:
        rows.append({
            "Assumption": "Comparison window start",
            "Value": anchor_window.effective_start_year,
            "Status": "Anchored",
            "Source": f"Anchor fund: {anchor_window.anchor_fund or 'N/A'}, "
                      f"anchor year: {anchor_window.anchor_start_year}, "
                      f"override: {anchor_window.override_start_year or 'none'}",
        })
    return assumptions, pd.DataFrame(rows)


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


def detect_fund_names_from_legacy(source: str | Path | IO) -> list[str]:
    """Return the list of fund names present in a legacy annual upload.

    This is a lightweight preview used to populate anchor/benchmark selectors
    in the UI before the full analysis is run.
    """
    df = read_uploaded_frame(source)
    if "Fund" not in df.columns:
        return []
    return sorted(df["Fund"].dropna().unique().tolist())


def build_legacy_analysis(
    source: str | Path | IO,
    risk_free_rate: float = DEFAULT_RISK_FREE,
    anchor_window: AnchorWindow | None = None,
    benchmark_fund: str | None = None,
) -> dict[str, Any]:
    """Compute legacy annual metrics and optional benchmark comparison for the UI.

    Parameters
    ----------
    source:
        File path or file-like object for the legacy annual CSV/Excel upload.
    risk_free_rate:
        Annualised risk-free rate.  Defaults to workbook value (2.0%).
    anchor_window:
        Optional :class:`AnchorWindow`.  When provided, all return series are
        clipped to ``effective_start_year`` before metric computation.
    benchmark_fund:
        Name of the fund column to use as benchmark.  May be any fund present
        in the upload (including the legacy ``SPX_Return``-derived ``SPX``
        column).  When ``None``, the ``SPX`` column is used if present.
    """
    returns_wide, benchmark_wide, meta = load_legacy_annual(source)

    # ── Anchor window — clip series to effective start year ──────────────────
    if anchor_window is not None:
        anchor_window.resolve_anchor(returns_wide)
        returns_wide = anchor_window.clip_to_window(returns_wide)
        benchmark_wide = anchor_window.clip_to_window(benchmark_wide)
        # Also clip meta to matching years
        if anchor_window.effective_start_year is not None:
            meta = meta.loc[meta["Year"].astype(int) >= anchor_window.effective_start_year]

    # ── Benchmark selection (first-class) ────────────────────────────────────
    # Priority: explicit benchmark_fund arg → SPX column from benchmark_wide
    benchmark_series: pd.Series | None = None
    resolved_benchmark_name: str | None = None

    if benchmark_fund is not None and benchmark_fund in returns_wide.columns:
        benchmark_series = returns_wide[benchmark_fund]
        resolved_benchmark_name = benchmark_fund
    elif benchmark_fund is not None and benchmark_fund in benchmark_wide.columns:
        benchmark_series = benchmark_wide[benchmark_fund]
        resolved_benchmark_name = benchmark_fund
    elif "SPX" in benchmark_wide.columns:
        benchmark_series = benchmark_wide["SPX"]
        resolved_benchmark_name = "SPX"

    # ── Raw data assembly ────────────────────────────────────────────────────
    raw_data_df = meta.copy()
    raw_data_df["Fund_Return"] = [
        returns_wide.loc[pd.Timestamp(f"{int(year)}-12-31"), fund]
        if pd.Timestamp(f"{int(year)}-12-31") in returns_wide.index
        and fund in returns_wide.columns
        else float("nan")
        for fund, year in zip(meta["Fund"], meta["Year"], strict=False)
    ]
    if benchmark_series is not None:
        raw_data_df["Benchmark_Return"] = [
            benchmark_series.loc[pd.Timestamp(f"{int(year)}-12-31")]
            if pd.Timestamp(f"{int(year)}-12-31") in benchmark_series.index
            else float("nan")
            for year in meta["Year"]
        ]

    # ── Metrics ──────────────────────────────────────────────────────────────
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
            cpi=DEFAULT_CPI,
            ips_target_spread=DEFAULT_IPS_SPREAD,
        )
        all_metrics[fund] = metrics

        if benchmark_series is not None and fund != resolved_benchmark_name:
            comparison = compute_annual_metrics_with_benchmark(
                series,
                benchmark_series,
                months_per_period=months_per_period,
                risk_free_rate=risk_free_rate,
                cpi=DEFAULT_CPI,
                ips_target_spread=DEFAULT_IPS_SPREAD,
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
        benchmark_name=resolved_benchmark_name,
        anchor_window=anchor_window,
    )

    combined_df = returns_wide.join(benchmark_wide, how="left") if not benchmark_wide.empty else returns_wide

    return {
        "returns_df": combined_df,
        "raw_data_df": raw_data_df,
        "all_metrics": all_metrics,
        "benchmark_comparison_df": pd.DataFrame(comparison_rows).T if comparison_rows else None,
        "assumptions": assumptions,
        "assumptions_df": assumptions_df,
        "has_benchmark": benchmark_series is not None,
        "benchmark_name": resolved_benchmark_name,
        # Keep legacy key for backwards-compat with existing export/test code
        "has_spx": "SPX" in benchmark_wide.columns,
        "fund_count": len(returns_wide.columns),
        "row_count": len(returns_wide),
    }


def build_monthly_benchmark_analysis(
    returns_df: pd.DataFrame,
    benchmark_col: str,
) -> pd.DataFrame:
    return compute_benchmark_comparison(returns_df, benchmark_col)
