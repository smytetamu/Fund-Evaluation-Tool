"""Basic smoke tests for metric calculations."""

import pandas as pd
import pytest

from fund_evaluation_tool.metrics import compute_metrics


def test_compute_metrics_basic():
    returns = pd.Series([0.01, -0.02, 0.03, 0.01, -0.01])
    m = compute_metrics(returns)
    assert "total_return" in m
    assert "sharpe_ratio" in m
    assert "max_drawdown" in m
    assert m["max_drawdown"] <= 0


def test_compute_metrics_empty():
    assert compute_metrics(pd.Series([], dtype=float)) == {}
