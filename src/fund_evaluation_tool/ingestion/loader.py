"""Load fund NAV/return data from CSV or Excel files."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Union

import pandas as pd


def load_fund_data(source: Union[str, Path, IO]) -> pd.DataFrame:
    """Load fund data from a CSV or Excel file or file-like object.

    Accepts:
    - A filesystem path (str or Path)
    - A Streamlit UploadedFile (has .name attribute)
    - A BytesIO / file-like object (name inferred from .name if present)

    Expected columns: date, fund_name, nav (or return).
    Returns a DataFrame with a DatetimeIndex.
    """
    # Determine the file name / extension
    if isinstance(source, (str, Path)):
        source = Path(source)
        name = source.name
    elif hasattr(source, "name"):
        # Streamlit UploadedFile or named file-like
        name = source.name
    else:
        # Anonymous BytesIO — can't infer type; default to CSV
        name = "data.csv"

    if name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(source)
    else:
        df = pd.read_csv(source)

    # Minimal normalisation — expand as needed
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    return df
