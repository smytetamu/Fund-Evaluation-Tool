"""Export results to a formatted Excel workbook."""

from pathlib import Path

import pandas as pd


def export_to_excel(
    metrics: dict[str, dict],
    output_path: str | Path = "fund_evaluation_report.xlsx",
) -> Path:
    """Write a metrics dict to an Excel file.

    Args:
        metrics: {fund_name: {metric: value}} mapping.
        output_path: Destination path for the .xlsx file.

    Returns:
        Resolved Path of the written file.
    """
    output_path = Path(output_path)
    df = pd.DataFrame(metrics).T
    df.index.name = "Fund"

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Metrics")

    return output_path.resolve()
