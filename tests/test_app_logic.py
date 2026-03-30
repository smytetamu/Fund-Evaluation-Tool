from pathlib import Path

from fund_evaluation_tool.app_logic import (
    build_legacy_analysis,
    detect_input_format,
    read_uploaded_frame,
)

FIXTURE = Path(__file__).parent / "fixtures" / "legacy_annual_returns.csv"
MONTHLY_FIXTURE = Path(__file__).parent / "fixtures" / "sample_returns.csv"


def test_detect_input_format_legacy_columns():
    df = read_uploaded_frame(FIXTURE)
    assert detect_input_format(df.columns) == "legacy_annual"


def test_detect_input_format_monthly_columns():
    df = read_uploaded_frame(MONTHLY_FIXTURE)
    assert detect_input_format(df.columns) == "monthly_wide"


def test_build_legacy_analysis_includes_ips_and_spx_comparison():
    result = build_legacy_analysis(FIXTURE)

    assert result["has_spx"] is True
    assert "HCI" in result["all_metrics"]
    assert "ips_compliant" in result["all_metrics"]["HCI"]
    assert result["benchmark_comparison_df"] is not None
    assert "excess_cagr" in result["benchmark_comparison_df"].columns
    assert "fund_ips_compliant" in result["benchmark_comparison_df"].columns
    assert result["raw_data_df"] is not None
    assert {"Fund", "Year", "Fund_Return", "SPX_Return"}.issubset(result["raw_data_df"].columns)
    assert result["assumptions"]["cpi"] == 0.03
    assert result["assumptions_df"] is not None
    assert {"Assumption", "Value", "Status", "Source"}.issubset(result["assumptions_df"].columns)
    fee_row = result["assumptions_df"].loc[
        result["assumptions_df"]["Assumption"] == "Fee treatment"
    ].iloc[0]
    assert fee_row["Value"] == "Gross / pre-fee returns"


def test_build_legacy_analysis_marks_partial_year_handling_in_assumptions():
    result = build_legacy_analysis(FIXTURE, risk_free_rate=0.04)

    partial_year_row = result["assumptions_df"].loc[
        result["assumptions_df"]["Assumption"] == "Partial-year handling"
    ].iloc[0]
    risk_free_row = result["assumptions_df"].loc[
        result["assumptions_df"]["Assumption"] == "Risk-free rate"
    ].iloc[0]

    assert partial_year_row["Value"] == "Included using Months_In_Period"
    assert risk_free_row["Value"] == 0.04
