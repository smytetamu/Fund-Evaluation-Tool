"""Scenario runner — filter a return series to a date sub-range."""

import pandas as pd

SCENARIOS = {
    "full": (None, None),
    "crisis_2008": ("2007-01-01", "2009-12-31"),
    "covid_2020": ("2020-01-01", "2020-12-31"),
}


def run_scenario(returns: pd.Series, scenario: str = "full") -> pd.Series:
    """Slice a return series to the given scenario window.

    Args:
        returns: Monthly return series with a DatetimeIndex.
        scenario: One of 'full', 'crisis_2008', 'covid_2020'.

    Returns:
        Sliced return series (may be empty if dates don't overlap).
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Valid: {list(SCENARIOS)}")

    start, end = SCENARIOS[scenario]
    if start is None:
        return returns
    return returns.loc[start:end]
