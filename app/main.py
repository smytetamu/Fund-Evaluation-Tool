"""Fund Evaluation Tool — Streamlit entrypoint."""

import io

import pandas as pd
import streamlit as st

from fund_evaluation_tool.app_logic import (
    build_legacy_analysis,
    build_monthly_benchmark_analysis,
    detect_input_format,
    read_uploaded_frame,
)
from fund_evaluation_tool.export import export_legacy_report_to_excel, export_to_excel
from fund_evaluation_tool.ingestion import load_fund_data
from fund_evaluation_tool.metrics import compute_metrics
from fund_evaluation_tool.scenarios import run_scenario

st.set_page_config(page_title="Fund Evaluation Tool", layout="wide")
st.title("📊 Fund Evaluation Tool")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    risk_free = st.number_input(
        "Risk-free rate (annualised)", value=0.04, step=0.005, format="%.3f"
    )
    scenario = st.selectbox("Scenario", ["full", "crisis_2008", "covid_2020"])

# ── Upload ────────────────────────────────────────────────────────────────────
st.header("1. Upload Fund Data")
st.caption("CSV with a `date` column + one numeric column per fund (monthly returns as decimals, e.g. 0.01 = 1%).")
uploaded = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])

if uploaded:
    uploaded_bytes = uploaded.getvalue()

    preview_buffer = io.BytesIO(uploaded_bytes)
    preview_buffer.name = uploaded.name
    preview_df = read_uploaded_frame(preview_buffer)
    input_format = detect_input_format(preview_df.columns)

    benchmark_comparison_df = None
    raw_data_df = None
    legacy_assumptions = None
    export_file_name = "fund_report.xlsx"

    if input_format == "legacy_annual":
        legacy_buffer = io.BytesIO(uploaded_bytes)
        legacy_buffer.name = uploaded.name
        legacy_result = build_legacy_analysis(legacy_buffer, risk_free_rate=risk_free)
        df = legacy_result["returns_df"]
        all_metrics = legacy_result["all_metrics"]
        benchmark_comparison_df = legacy_result["benchmark_comparison_df"]
        numeric_cols = [c for c in df.select_dtypes("number").columns.tolist() if c != "SPX"]
        raw_data_df = legacy_result["raw_data_df"]
        legacy_assumptions = legacy_result["assumptions"]
        export_file_name = "fund_legacy_report.xlsx"

        st.success(
            f"Detected legacy annual format. Loaded {legacy_result['row_count']} annual rows, "
            f"{legacy_result['fund_count']} fund(s)."
        )
        st.caption("Legacy annual uploads are analysed with annual metrics. Monthly scenario filters do not apply.")
        st.dataframe(df.head(20))

        st.header("2. Annual Metrics")
        if not numeric_cols:
            st.warning("No fund return columns found in the legacy upload.")
        else:
            metrics_df = pd.DataFrame(all_metrics).T
            metrics_df.index.name = "Fund"
            metrics_df.columns = [c.replace("_", " ").title() for c in metrics_df.columns]
            st.dataframe(metrics_df, use_container_width=True)

            if "Ips Compliant" in metrics_df.columns:
                ips_df = metrics_df[[c for c in ["Cagr", "Ips Target", "Ips Delta", "Ips Compliant"] if c in metrics_df.columns]].copy()
                st.subheader("IPS Compliance")
                st.dataframe(ips_df, use_container_width=True)

        if legacy_result["has_spx"] and benchmark_comparison_df is not None and not benchmark_comparison_df.empty:
            st.header("3. Fund vs SPX")
            display_df = benchmark_comparison_df.copy()
            display_df.index.name = "Fund"
            display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]
            st.dataframe(display_df, use_container_width=True)
            st.caption("Annual comparison aligns each fund with the shared SPX annual series and highlights CAGR, excess CAGR, and IPS flags.")

        export_header = "4. Export" if legacy_result["has_spx"] else "3. Export"
    else:
        # Pass the UploadedFile directly — loader now handles file-like objects
        monthly_buffer = io.BytesIO(uploaded_bytes)
        monthly_buffer.name = uploaded.name
        df = load_fund_data(monthly_buffer)
        numeric_cols = df.select_dtypes("number").columns.tolist()
        st.success(f"Loaded {len(df)} rows, {len(numeric_cols)} fund(s).")
        st.dataframe(df.head(20))

        # ── Benchmark selection ───────────────────────────────────────────────
        st.header("2. Benchmark (optional)")
        benchmark_options = ["None"] + numeric_cols
        benchmark_col = st.selectbox(
            "Select a column to use as benchmark",
            options=benchmark_options,
            help="The selected column will be used as the benchmark for comparison. "
                 "It will still appear in the metrics table.",
        )
        use_benchmark = benchmark_col != "None"

        # ── Metrics ───────────────────────────────────────────────────────────
        st.header("3. Metrics")
        all_metrics: dict[str, dict] = {}

        if not numeric_cols:
            st.warning("No numeric columns found. Check that your file has return data.")
        else:
            for col in numeric_cols:
                series = df[col].dropna()
                m = compute_metrics(series, risk_free_rate=risk_free)
                run_scenario(series, scenario=scenario)
                all_metrics[col] = m

            metrics_df = pd.DataFrame(all_metrics).T
            metrics_df.index.name = "Fund"
            metrics_df.columns = [c.replace("_", " ").title() for c in metrics_df.columns]

            st.dataframe(
                metrics_df.style.format("{:.4f}"),
                use_container_width=True,
            )

            if scenario != "full":
                st.caption(f"⚠️ Scenario filter **{scenario}** applied to scenario calc only. "
                           "Table above shows full-period metrics.")

        # ── Benchmark comparison ──────────────────────────────────────────────
        if use_benchmark and numeric_cols:
            st.header("4. Benchmark Comparison")
            st.caption(f"Benchmark: **{benchmark_col}**")

            benchmark_comparison_df = build_monthly_benchmark_analysis(df, benchmark_col)

            display_df = benchmark_comparison_df.copy()
            display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]

            st.dataframe(
                display_df.style.format("{:.4f}"),
                use_container_width=True,
            )
            st.caption(
                "**Excess Return** = fund annualised return − benchmark annualised return. "
                "**Tracking Error** = annualised std of monthly return differences. "
                "**Information Ratio** = excess return / tracking error. "
                "**Alpha** = Jensen-style annualised alpha."
            )

        export_header = "5. Export" if use_benchmark else "4. Export"

    # ── Export ────────────────────────────────────────────────────────────────
    st.header(export_header)

    excel_buf = io.BytesIO()
    if input_format == "legacy_annual":
        export_legacy_report_to_excel(
            all_metrics,
            raw_data_df=raw_data_df if raw_data_df is not None else pd.DataFrame(),
            output=excel_buf,
            comparison_df=benchmark_comparison_df,
            assumptions=legacy_assumptions,
        )
    else:
        export_to_excel(all_metrics, excel_buf, benchmark_df=benchmark_comparison_df)
    excel_buf.seek(0)

    st.download_button(
        label="📥 Download Excel Report",
        data=excel_buf,
        file_name=export_file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Upload a CSV or Excel file to get started.")
    with st.expander("Expected file format"):
        st.markdown("""
| date       | FundA | FundB | Benchmark |
|------------|-------|-------|-----------|
| 2020-01-31 | 0.012 | -0.005 | 0.008 |
| 2020-02-29 | -0.032| -0.081 | -0.040 |
| ...        | ...   | ...   | ... |

- `date` column is required (any parseable date format)
- Each additional column = one fund's **monthly returns** (as decimals)
- Select any column as **benchmark** to get relative comparison metrics
- Missing values are dropped automatically
        """)
