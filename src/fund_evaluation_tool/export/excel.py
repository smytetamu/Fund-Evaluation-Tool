"""Export results to a formatted Excel workbook."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Union

import pandas as pd


def export_to_excel(
    metrics: dict[str, dict],
    output: Union[str, Path, IO] = "fund_evaluation_report.xlsx",
    benchmark_df: "pd.DataFrame | None" = None,
) -> Union[Path, IO]:
    """Write a metrics dict to an Excel file or file-like object.

    Args:
        metrics: {fund_name: {metric: value}} mapping.
        output: Destination path, BytesIO, or other writable file-like object.
        benchmark_df: Optional DataFrame from compute_benchmark_comparison to add
            a "Benchmark Comparison" sheet.

    Returns:
        Resolved Path if a path was given, else the file-like object.
    """
    df = pd.DataFrame(metrics).T
    df.index.name = "Fund"
    # Friendly column names
    df.columns = [c.replace("_", " ").title() for c in df.columns]

    is_path = isinstance(output, (str, Path))
    if is_path:
        output = Path(output)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Metrics")

        # Basic column width auto-fit
        ws = writer.sheets["Metrics"]
        for col_cells in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 40)

        if benchmark_df is not None and not benchmark_df.empty:
            bdf = benchmark_df.copy()
            bdf.columns = [c.replace("_", " ").title() for c in bdf.columns]
            bdf.to_excel(writer, sheet_name="Benchmark Comparison")
            ws2 = writer.sheets["Benchmark Comparison"]
            for col_cells in ws2.columns:
                max_len = max(len(str(cell.value or "")) for cell in col_cells)
                ws2.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 40)

    return output.resolve() if is_path else output
