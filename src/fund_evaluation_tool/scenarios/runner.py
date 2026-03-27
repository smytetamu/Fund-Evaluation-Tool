"""Scenario runner — apply shocks or slices to a return series."""

import pandas as pd

from fund_evaluation_tool.metrics import compute_metrics


def run_scenario(
    returns: pd.Series,
    scenario: str = "full",
    shock: float = 0.0,
) -> dict:
    """Run a named scenario on a return series.

    Args:
        returns: Full return series.
        scenario: One of 'full', 'crisis_2008', 'covid_2020', or 'custom'.
        shock: Additional return shock applied to every period (default 0).

    Returns:
        Metrics dict for the scenario.
    """
    SLICES = {
        "crisis_2008": ("2008-01", "2009-03"),
        "covid_2020": ("2020-02", "2020-12"),
    }

    if scenario in SLICES:
        start, end = SLICES[scenario]
        series = returns.loc[start:end]
    else:
        series = returns.copy()

    if shock:
        series = series + shock

    return compute_metrics(series)
