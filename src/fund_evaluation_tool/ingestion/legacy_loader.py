"""Load legacy annual long-format fund data and normalise for the metrics flow.

Legacy CSV schema (HCI_Fund_Performance_Extract.csv shape):
    Fund, Year, Fund_Return, SPX_Return, Is_Partial_Year, Months_In_Period,
    Fee_Mode, Mgmt_Fee_%, Perf_Fee_%, Hurdle_Type, Hurdle_Value,
    HWM_Enabled, Source_Notes

Only the first six columns are required; the rest are preserved but not
used by the normalisation step.

Returns
-------
``load_legacy_annual`` → wide-format DataFrame (DatetimeIndex, one column per
fund), plus a separate wide-format DataFrame for the SPX benchmark and a
metadata dict carrying partial-year flags.

``normalise_legacy_for_metrics`` → the wide-format returns DataFrame, ready
to feed into ``compute_metrics`` / the comparison flow.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Union

import pandas as pd


_REQUIRED_COLS = {"Fund", "Year", "Fund_Return"}
_BENCHMARK_COL = "SPX_Return"
_PARTIAL_FLAG = "Is_Partial_Year"
_MONTHS_COL = "Months_In_Period"


def _is_legacy_long_format(df: pd.DataFrame) -> bool:
    """Return True if df looks like the annual long-format legacy shape."""
    return _REQUIRED_COLS.issubset(set(df.columns))


def load_legacy_annual(
    source: Union[str, Path, IO],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load a legacy annual long-format CSV.

    Parameters
    ----------
    source:
        Path to CSV, or file-like object.

    Returns
    -------
    returns_wide : pd.DataFrame
        Annual fund returns, one column per fund, indexed by year-end date
        (31 Dec of that year).  Values are decimals (0.365 = 36.5%).
    benchmark_wide : pd.DataFrame
        Same shape but contains the SPX_Return column for each fund row.
        Since SPX is the same for every fund in a given year this collapses
        to a single column ``SPX`` indexed by year-end date.  Empty DataFrame
        if SPX_Return is absent.
    meta : pd.DataFrame
        Long-format metadata: Fund, Year, Is_Partial_Year, Months_In_Period.
    """
    if isinstance(source, (str, Path)):
        df = pd.read_csv(source)
    else:
        df = pd.read_csv(source)

    if not _is_legacy_long_format(df):
        raise ValueError(
            "File does not look like legacy annual long format. "
            f"Expected columns including {_REQUIRED_COLS}; "
            f"got {list(df.columns)}"
        )

    # Coerce types
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df["Fund_Return"] = pd.to_numeric(df["Fund_Return"], errors="coerce")
    df = df.dropna(subset=["Fund", "Year", "Fund_Return"])

    # Year-end date index: Dec 31 of each year
    df["date"] = pd.to_datetime(df["Year"].astype(str) + "-12-31")

    # --- Wide fund returns ---
    returns_wide = (
        df.pivot_table(index="date", columns="Fund", values="Fund_Return", aggfunc="first")
        .rename_axis(None, axis=1)
        .sort_index()
    )

    # --- Benchmark wide ---
    if _BENCHMARK_COL in df.columns:
        df[_BENCHMARK_COL] = pd.to_numeric(df[_BENCHMARK_COL], errors="coerce")
        spx_series = (
            df.groupby("date")[_BENCHMARK_COL].first()
            .rename("SPX")
            .to_frame()
        )
        benchmark_wide = spx_series
    else:
        benchmark_wide = pd.DataFrame()

    # --- Metadata ---
    meta_cols = ["Fund", "Year"]
    if _PARTIAL_FLAG in df.columns:
        meta_cols.append(_PARTIAL_FLAG)
    if _MONTHS_COL in df.columns:
        meta_cols.append(_MONTHS_COL)
    meta = df[meta_cols].copy().reset_index(drop=True)

    return returns_wide, benchmark_wide, meta


def normalise_legacy_for_metrics(
    source: Union[str, Path, IO],
    include_benchmark: bool = True,
) -> pd.DataFrame:
    """High-level helper: load legacy CSV and return a single wide DataFrame.

    The result merges fund returns and (optionally) the SPX benchmark column
    into one DataFrame with a DatetimeIndex, ready for ``compute_metrics`` or
    the benchmark comparison flow.

    Parameters
    ----------
    source:
        Path to CSV or file-like.
    include_benchmark:
        If True (default) and SPX_Return is present, an ``SPX`` column is
        appended to the returned DataFrame.

    Returns
    -------
    pd.DataFrame — wide format, DatetimeIndex (annual, Dec 31).
    """
    returns_wide, benchmark_wide, _ = load_legacy_annual(source)

    if include_benchmark and not benchmark_wide.empty:
        combined = returns_wide.join(benchmark_wide, how="left")
    else:
        combined = returns_wide

    return combined
