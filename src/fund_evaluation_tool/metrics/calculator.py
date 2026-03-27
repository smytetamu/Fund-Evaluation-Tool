"""Core metric calculations for a return series."""

import numpy as np
import pandas as pd


def compute_metrics(returns: pd.Series, risk_free_rate: float = 0.0) -> dict:
    """Compute standard fund performance metrics.

    Args:
        returns: Periodic return series (e.g. monthly, daily).
        risk_free_rate: Annualised risk-free rate (default 0).

    Returns:
        Dict of metric name → value.
    """
    if returns.empty:
        return {}

    ann_factor = 12  # assume monthly; TODO: infer from frequency

    total_return = (1 + returns).prod() - 1
    ann_return = (1 + total_return) ** (ann_factor / len(returns)) - 1
    ann_vol = returns.std() * np.sqrt(ann_factor)
    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol else np.nan

    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    return {
        "total_return": total_return,
        "annualised_return": ann_return,
        "annualised_volatility": ann_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
    }
