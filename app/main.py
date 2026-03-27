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
    risk_free = st.number_input("Risk-free rate (annualised)", value=0.04, step=0.005, format="%.3f")
    scenario = st.selectbox("Scenario", ["full", "crisis_2008", "covid_2020"])

# ── Upload ────────────────────────────────────────────────────────────────────
st.header("1. Upload Fund Data")
uploaded = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])

if uploaded:
    df = load_fund_data(io.BytesIO(uploaded.read()) if uploaded.name.endswith(".csv") else uploaded)
    st.dataframe(df.head(20))

    # ── Metrics ───────────────────────────────────────────────────────────────
    st.header("2. Metrics")
    all_metrics: dict[str, dict] = {}

    for col in df.select_dtypes("number").columns:
        m = run_scenario(df[col].dropna(), scenario=scenario)
        m_full = compute_metrics(df[col].dropna(), risk_free_rate=risk_free)
        all_metrics[col] = m_full

    metrics_df = pd.DataFrame(all_metrics).T
    st.dataframe(metrics_df.style.format("{:.4f}"))

    # ── Export ────────────────────────────────────────────────────────────────
    st.header("3. Export")
    if st.button("Download Excel Report"):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = export_to_excel(all_metrics, tmp.name)
        with open(path, "rb") as f:
            st.download_button("📥 Download", f, file_name="fund_report.xlsx")
        os.unlink(path)
else:
    st.info("Upload a file to get started.")
