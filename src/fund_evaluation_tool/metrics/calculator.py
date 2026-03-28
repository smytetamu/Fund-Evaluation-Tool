"""Core metric calculations for a monthly return series."""

import numpy as np
import pandas as pd

ANN_FACTOR = 12  # monthly data


def compute_metrics(returns: pd.Series, risk_free_rate: float = 0.0) -> dict:
    """Compute standard fund performance metrics from a monthly return series.

    Args:
        returns: Monthly return series as decimals (e.g. 0.01 for 1%).
        risk_free_rate: Annualised risk-free rate (default 0.0).

    Returns:
        Dict of metric name → float value.
    """
    returns = returns.dropna()
    if returns.empty:
        return {}

    n = len(returns)

    # Total return
    total_return = float((1 + returns).prod() - 1)

    # Annualised return (CAGR equivalent)
    ann_return = float((1 + total_return) ** (ANN_FACTOR / n) - 1)

    # Annualised volatility
    ann_vol = float(returns.std() * np.sqrt(ANN_FACTOR))

    # Sharpe ratio (annualised)
    sharpe = float((ann_return - risk_free_rate) / ann_vol) if ann_vol > 0 else float("nan")

    # Maximum drawdown
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_drawdown = float(drawdown.min())

    # Calmar ratio (ann return / abs max drawdown)
    calmar = float(ann_return / abs(max_drawdown)) if max_drawdown < 0 else float("nan")

    return {
        "total_return": total_return,
        "annualised_return": ann_return,
        "annualised_volatility": ann_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "calmar_ratio": calmar,
        "num_periods": n,
    }
