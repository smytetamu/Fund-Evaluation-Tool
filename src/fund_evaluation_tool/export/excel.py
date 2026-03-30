"""Export results to a formatted Excel workbook."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Union

import pandas as pd


def _auto_fit_worksheet(worksheet) -> None:
    """Apply a basic width fit for populated columns."""
    for col_cells in worksheet.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        worksheet.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 40)


def _friendly_columns(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    formatted.columns = [c.replace("_", " ").title() for c in formatted.columns]
    return formatted


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
    df = _friendly_columns(df)

    is_path = isinstance(output, (str, Path))
    if is_path:
        output = Path(output)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Metrics")
        _auto_fit_worksheet(writer.sheets["Metrics"])

        if benchmark_df is not None and not benchmark_df.empty:
            bdf = _friendly_columns(benchmark_df)
            bdf.to_excel(writer, sheet_name="Benchmark Comparison")
            _auto_fit_worksheet(writer.sheets["Benchmark Comparison"])

    return output.resolve() if is_path else output


def export_legacy_report_to_excel(
    metrics: dict[str, dict[str, Any]],
    raw_data_df: pd.DataFrame,
    output: Union[str, Path, IO] = "fund_evaluation_legacy_report.xlsx",
    comparison_df: pd.DataFrame | None = None,
    assumptions: dict[str, Any] | pd.DataFrame | None = None,
) -> Union[Path, IO]:
    """Write a legacy annual report workbook for demo/reporting flows.

    Sheets:
    - Comparison: annual fund/SPX comparison and IPS flags
    - Raw Data: annual rows used for the analysis
    - Assumptions: optional placeholder/default assumptions
    """
    comparison_export = comparison_df.copy() if comparison_df is not None else pd.DataFrame(metrics).T
    comparison_export.index.name = "Fund"
    comparison_export = _friendly_columns(comparison_export.reset_index())

    raw_export = raw_data_df.copy()
    if not raw_export.empty:
        ordered_cols = [
            col
            for col in [
                "Fund",
                "Year",
                "Fund_Return",
                "SPX_Return",
                "Is_Partial_Year",
                "Months_In_Period",
            ]
            if col in raw_export.columns
        ]
        remaining_cols = [col for col in raw_export.columns if col not in ordered_cols]
        raw_export = raw_export[ordered_cols + remaining_cols]
    raw_export = _friendly_columns(raw_export)

    assumptions_export: pd.DataFrame | None = None
    if assumptions is not None:
        if isinstance(assumptions, pd.DataFrame):
            assumptions_export = assumptions.copy()
        else:
            assumptions_export = pd.DataFrame(
                [{"Assumption": key, "Value": value} for key, value in assumptions.items()]
            )
    if assumptions_export is not None and not assumptions_export.empty:
        preferred_cols = [
            col for col in ["Assumption", "Value", "Status", "Source"] if col in assumptions_export.columns
        ]
        remaining_cols = [col for col in assumptions_export.columns if col not in preferred_cols]
        assumptions_export = assumptions_export[preferred_cols + remaining_cols]

    is_path = isinstance(output, (str, Path))
    if is_path:
        output = Path(output)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        comparison_export.to_excel(writer, sheet_name="Comparison", index=False)
        _auto_fit_worksheet(writer.sheets["Comparison"])

        raw_export.to_excel(writer, sheet_name="Raw Data", index=False)
        _auto_fit_worksheet(writer.sheets["Raw Data"])

        if assumptions_export is not None and not assumptions_export.empty:
            assumptions_export.to_excel(writer, sheet_name="Assumptions", index=False)
            _auto_fit_worksheet(writer.sheets["Assumptions"])

    return output.resolve() if is_path else output
