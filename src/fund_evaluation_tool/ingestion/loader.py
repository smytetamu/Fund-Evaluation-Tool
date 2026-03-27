"""Load fund NAV/return data from CSV or Excel files."""

from pathlib import Path

import pandas as pd


def load_fund_data(path: str | Path) -> pd.DataFrame:
    """Load fund data from a CSV or Excel file.

    Expected columns: date, fund_name, nav (or return).
    Returns a DataFrame with a DatetimeIndex.
    """
    path = Path(path)
    if path.suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    # Minimal normalisation — expand as needed
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    return df
