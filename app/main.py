"""Fund Evaluation Tool — Streamlit entrypoint."""

import io

import pandas as pd
import streamlit as st

from fund_evaluation_tool.export import export_to_excel
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
    # Pass the UploadedFile directly — loader now handles file-like objects
    df = load_fund_data(uploaded)
    st.success(f"Loaded {len(df)} rows, {len(df.select_dtypes('number').columns)} fund(s).")
    st.dataframe(df.head(20))

    # ── Metrics ───────────────────────────────────────────────────────────────
    st.header("2. Metrics")
    all_metrics: dict[str, dict] = {}
    numeric_cols = df.select_dtypes("number").columns.tolist()

    if not numeric_cols:
        st.warning("No numeric columns found. Check that your file has return data.")
    else:
        for col in numeric_cols:
            series = df[col].dropna()
            m = compute_metrics(series, risk_free_rate=risk_free)
            scenario_m = run_scenario(series, scenario=scenario)
            # Show full-period metrics; scenario info available in tooltip / future tab
            all_metrics[col] = m

        metrics_df = pd.DataFrame(all_metrics).T
        metrics_df.index.name = "Fund"

        # Friendly column labels
        metrics_df.columns = [c.replace("_", " ").title() for c in metrics_df.columns]

        st.dataframe(
            metrics_df.style.format("{:.4f}"),
            use_container_width=True,
        )

        if scenario != "full":
            st.caption(f"⚠️ Scenario filter **{scenario}** applied to scenario calc only. "
                       "Table above shows full-period metrics.")

        # ── Export ────────────────────────────────────────────────────────────
        st.header("3. Export")

        # Build Excel in-memory so we don't touch the filesystem
        excel_buf = io.BytesIO()
        export_to_excel(all_metrics, excel_buf)
        excel_buf.seek(0)

        st.download_button(
            label="📥 Download Excel Report",
            data=excel_buf,
            file_name="fund_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Upload a CSV or Excel file to get started.")
    with st.expander("Expected file format"):
        st.markdown("""
| date       | FundA | FundB |
|------------|-------|-------|
| 2020-01-31 | 0.012 | -0.005 |
| 2020-02-29 | -0.032| -0.081 |
| ...        | ...   | ...   |

- `date` column is required (any parseable date format)
- Each additional column = one fund's **monthly returns** (as decimals)
- Missing values are dropped automatically
        """)
