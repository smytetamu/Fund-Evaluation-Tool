"""Benchmark comparison calculations."""

from __future__ import annotations

import pandas as pd


def compute_benchmark_comparison(
    returns_df: pd.DataFrame,
    benchmark_col: str,
) -> pd.DataFrame:
    """Compute benchmark-relative statistics for each fund vs a benchmark column.

    Args:
        returns_df: DataFrame with monthly return columns (funds + benchmark).
        benchmark_col: Column name to treat as benchmark.

    Returns:
        DataFrame indexed by fund name with columns:
            - fund_ann_return: Annualised return of the fund
            - benchmark_ann_return: Annualised return of the benchmark
            - excess_return: fund_ann_return - benchmark_ann_return
            - tracking_error: Annualised std of monthly return differences
            - information_ratio: excess_return / tracking_error (NaN if zero vol)
            - beta: fund/benchmark beta (covariance / benchmark variance)
            - alpha: Jensen's alpha (monthly, annualised)
            - correlation: rolling Pearson correlation with benchmark
    """
    bench = returns_df[benchmark_col].dropna()

    def _ann_return(s: pd.Series) -> float:
        s = s.dropna()
        if len(s) == 0:
            return float("nan")
        total = (1 + s).prod()
        return total ** (12 / len(s)) - 1

    bench_ann = _ann_return(bench)

    rows: dict[str, dict] = {}

    fund_cols = [c for c in returns_df.select_dtypes("number").columns if c != benchmark_col]

    for col in fund_cols:
        fund = returns_df[col].dropna()

        # Align on shared index
        aligned = pd.concat([fund, bench], axis=1, join="inner").dropna()
        aligned.columns = ["fund", "bench"]

        if len(aligned) == 0:
            rows[col] = {
                "fund_ann_return": float("nan"),
                "benchmark_ann_return": bench_ann,
                "excess_return": float("nan"),
                "tracking_error": float("nan"),
                "information_ratio": float("nan"),
                "beta": float("nan"),
                "alpha": float("nan"),
                "correlation": float("nan"),
            }
            continue

        fund_ann = _ann_return(aligned["fund"])
        excess = fund_ann - bench_ann

        monthly_diff = aligned["fund"] - aligned["bench"]
        te = monthly_diff.std() * (12 ** 0.5)

        ir = excess / te if te and te > 1e-12 else float("nan")

        bench_var = aligned["bench"].var()
        if bench_var and bench_var > 1e-12:
            beta = aligned["fund"].cov(aligned["bench"]) / bench_var
        else:
            beta = float("nan")

        # Alpha: annualised (Jensen-style, simplified)
        if not (beta != beta):  # beta is not NaN
            monthly_alpha = aligned["fund"].mean() - beta * aligned["bench"].mean()
            alpha = monthly_alpha * 12
        else:
            alpha = float("nan")

        corr = aligned["fund"].corr(aligned["bench"])

        rows[col] = {
            "fund_ann_return": fund_ann,
            "benchmark_ann_return": bench_ann,
            "excess_return": excess,
            "tracking_error": te,
            "information_ratio": ir,
            "beta": beta,
            "alpha": alpha,
            "correlation": corr,
        }

    result = pd.DataFrame(rows).T
    result.index.name = "Fund"
    return result
