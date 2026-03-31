"""Fund Evaluation Tool — Streamlit entrypoint."""

from __future__ import annotations

import io
import os

import pandas as pd
import streamlit as st

import plotly.express as px

from fund_evaluation_tool.app_logic import (
    DEFAULT_RISK_FREE,
    build_legacy_analysis,
    build_monthly_benchmark_analysis,
    compute_dashboard_summary,
    compute_wealth_growth,
    detect_input_format,
    detect_fund_names_from_legacy,
    read_uploaded_frame,
)
from fund_evaluation_tool.export import export_legacy_report_to_excel, export_to_excel
from fund_evaluation_tool.fund_details import AnchorWindow, FundDetails, FundDetailsConfig
from fund_evaluation_tool.ingestion import load_fund_data
from fund_evaluation_tool.ingestion.pdf_extractor import (
    extract_fund_data_from_pdf,
    rows_to_legacy_csv_bytes,
    _LEGACY_COLUMNS,
)
from fund_evaluation_tool.metrics import compute_metrics
from fund_evaluation_tool.scenarios import run_scenario

st.set_page_config(page_title="Fund Evaluation Tool", layout="wide")
st.title("📊 Fund Evaluation Tool")

# ── Session state initialisation ─────────────────────────────────────────────
if "fund_details_config" not in st.session_state:
    st.session_state.fund_details_config = FundDetailsConfig()
if "anchor_window" not in st.session_state:
    st.session_state.anchor_window = AnchorWindow()
if "pasted_raw_data" not in st.session_state:
    st.session_state.pasted_raw_data = ""

# ── Instructions panel ────────────────────────────────────────────────────────
with st.expander("ℹ️ How to Use This Tool", expanded=False):
    st.markdown("""
**Step 1 — Prepare your fund data**

You need performance data in one of two formats:
- **Legacy annual format** — long CSV with columns: `Fund`, `Year`, `Fund_Return`, `SPX_Return` (optional), `Months_In_Period` (optional)
- **Monthly wide format** — wide CSV with a `date` column plus one decimal-return column per fund

If you have PDF tear-sheets or reports, use the **AI Extraction Prompt Template** (below) with Claude to convert them into structured CSV rows automatically.

**Step 2 — Import data**

- **Upload a file** (CSV or Excel) using the Upload tab, or
- **Paste CSV rows** directly into the Paste tab — no file needed

**Step 3 — Configure fund details** *(legacy format only)*

After import, open **Fund Details Configuration** to set strategy type, return type, fee terms, and source notes per fund.
You can also bulk-import fund metadata from AI-extracted CSV using the **Import Fund Details CSV** section inside that panel.

**Step 4 — Review analysis**

- **Dashboard summary** — active fund count, best CAGR/Sharpe, IPS compliance, benchmark-beating count
- **Wealth Growth chart** — cumulative $1M growth across all included funds
- **Annual Metrics** — CAGR, Sharpe, Sortino, IPS target compliance
- **Benchmark Comparison** — excess CAGR and IPS status vs selected benchmark

**Step 5 — Export**

Download a formatted Excel report with Comparison, Raw Data, Assumptions, and Fund Details sheets.
""")

# ── AI extraction prompt template ─────────────────────────────────────────────
with st.expander("🤖 AI Extraction Prompt Template", expanded=False):
    st.caption(
        "Copy either prompt below and use it with Claude (claude.ai or API) "
        "to extract structured data from fund PDFs. Paste the output into the **Paste** tab."
    )

    st.markdown("**Performance Data (Raw_Data)**")
    st.code(
        """\
You are a financial data extraction assistant. Extract fund performance data from the \
provided document and output it in CSV format with these exact columns:

Fund,Year,Fund_Return,SPX_Return,Months_In_Period

Rules:
- Fund: the fund name (keep consistent across all rows for the same fund)
- Year: 4-digit calendar year (e.g. 2023)
- Fund_Return: annual return as a decimal (e.g. 0.15 for 15%, -0.08 for -8%)
- SPX_Return: S&P 500 return for that year as a decimal (leave blank if not in document)
- Months_In_Period: number of months in the period (12 for full years; fewer for partial years)

Output only the CSV rows with the header line and no other text.

Example output:
Fund,Year,Fund_Return,SPX_Return,Months_In_Period
MyFund,2020,0.152,0.184,12
MyFund,2021,0.089,0.287,12
MyFund,2022,-0.043,-0.181,12""",
        language="text",
    )

    st.markdown("**Fund Metadata (Fund_Details)**")
    st.code(
        """\
You are a financial data extraction assistant. Extract fund configuration metadata from \
the provided document and output it in CSV format with these exact columns:

Fund,Strategy,ReturnType,ManagementFee,PerformanceFee,HurdleRate,HWM,LiquidityNotes,SourceNote

Rules:
- Fund: must match the name used in performance data exactly
- Strategy: one of [Equity Long/Short, Equity Long Only, Fixed Income, Multi-Strategy, \
Global Macro, Event Driven, Real Assets, Private Equity, Other]
- ReturnType: Gross or Net
- ManagementFee: as decimal (0.02 = 2%); leave blank if unknown
- PerformanceFee: as decimal (0.20 = 20%); leave blank if unknown
- HurdleRate: as decimal (0.08 = 8%); leave blank if unknown
- HWM: TRUE or FALSE
- LiquidityNotes: brief text on redemption terms (e.g. "Quarterly with 45-day notice")
- SourceNote: source document name or date (e.g. "Q4 2023 Tear Sheet")

Output only the CSV rows with the header line and no other text.""",
        language="text",
    )

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    risk_free = st.number_input(
        "Risk-free rate (annualised)",
        value=DEFAULT_RISK_FREE,
        step=0.005,
        format="%.3f",
        help="Workbook default: 2.0%. Used for Sharpe and Sortino ratios.",
    )
    scenario = st.selectbox("Scenario", ["full", "crisis_2008", "covid_2020"])

# ── PDF Import ────────────────────────────────────────────────────────────────
with st.expander("📄 Import from Fund Document (PDF)", expanded=False):
    st.markdown(
        "Upload a fund tear sheet, quarterly letter, or performance report PDF. "
        "Claude AI will extract the fund performance data automatically. "
        "Review and edit the results, then download as CSV to use in the analysis below."
    )

    pdf_api_key = st.text_input(
        "Anthropic API key",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Required to call Claude for PDF extraction. Set ANTHROPIC_API_KEY env var to pre-fill.",
    )

    uploaded_pdf = st.file_uploader(
        "Upload PDF fund document",
        type=["pdf"],
        key="pdf_uploader",
    )

    if uploaded_pdf and st.button("Extract data from PDF", type="primary"):
        if not pdf_api_key:
            st.error("Please enter an Anthropic API key above.")
        else:
            with st.spinner("Sending PDF to Claude for extraction…"):
                try:
                    pdf_bytes = uploaded_pdf.getvalue()
                    rows = extract_fund_data_from_pdf(pdf_bytes, api_key=pdf_api_key)
                    st.session_state["pdf_extracted_rows"] = rows
                    st.success(
                        f"Extracted {len(rows)} row(s) from **{uploaded_pdf.name}**. "
                        "Review below and correct any errors before downloading."
                    )
                except ValueError as exc:
                    st.error(f"Extraction failed: {exc}")
                    st.session_state.pop("pdf_extracted_rows", None)

    if "pdf_extracted_rows" in st.session_state:
        raw_rows = st.session_state["pdf_extracted_rows"]
        extracted_df = pd.DataFrame(raw_rows, columns=_LEGACY_COLUMNS)

        st.subheader("Extracted data — review & edit")
        st.caption(
            "Returns are decimals (0.15 = 15%). Edit any cell before downloading. "
            "Add or delete rows as needed."
        )

        edited_df = st.data_editor(
            extracted_df,
            num_rows="dynamic",
            use_container_width=True,
            key="pdf_editor",
        )

        csv_bytes = rows_to_legacy_csv_bytes(edited_df.to_dict("records"))
        st.download_button(
            label="📥 Download extracted data as CSV",
            data=csv_bytes,
            file_name="extracted_fund_data.csv",
            mime="text/csv",
            help="Download the reviewed data, then upload it in the section below to run the analysis.",
        )

        st.info(
            "After downloading, upload the CSV in **'1. Input Fund Data'** below to run metrics and analysis."
        )

# ── Input Fund Data ───────────────────────────────────────────────────────────
st.header("1. Input Fund Data")
st.caption(
    "Upload a file **or** paste AI-extracted CSV rows. "
    "Legacy annual format: `Fund, Year, Fund_Return` columns. "
    "Monthly format: `date` + one column per fund (decimal returns)."
)

upload_tab, paste_tab = st.tabs(["📁 Upload File", "📋 Paste CSV"])

with upload_tab:
    uploaded = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])

with paste_tab:
    st.caption(
        "Paste rows in legacy annual format (Fund, Year, Fund_Return, ...). "
        "Use the AI Extraction Prompt Template above to generate these rows from a PDF."
    )
    pasted_text = st.text_area(
        "Paste CSV rows here",
        height=180,
        placeholder=(
            "Fund,Year,Fund_Return,SPX_Return,Months_In_Period\n"
            "FundA,2020,0.15,0.18,12\n"
            "FundA,2021,0.08,0.29,12"
        ),
        key="paste_text_area",
    )
    if st.button("Load Pasted Data", type="primary"):
        st.session_state.pasted_raw_data = pasted_text.strip()
        st.rerun()
    if st.session_state.pasted_raw_data:
        st.success("Pasted data loaded — scroll down to see analysis.")
        if st.button("Clear pasted data"):
            st.session_state.pasted_raw_data = ""
            st.rerun()

# ── Determine data source ─────────────────────────────────────────────────────
_pasted = st.session_state.get("pasted_raw_data", "").strip()
_has_data = bool(uploaded or _pasted)

if _has_data:
    if uploaded:
        raw_bytes = uploaded.getvalue()
        file_name = uploaded.name
    else:
        raw_bytes = _pasted.encode("utf-8")
        file_name = "pasted_data.csv"

    preview_buffer = io.BytesIO(raw_bytes)
    preview_buffer.name = file_name
    preview_df = read_uploaded_frame(preview_buffer)
    input_format = detect_input_format(preview_df.columns)

    benchmark_comparison_df = None
    raw_data_df = None
    legacy_assumptions = None
    legacy_assumptions_df = None
    export_file_name = "fund_report.xlsx"

    if input_format == "legacy_annual":
        # ── Detect fund names for sidebar controls ────────────────────────────
        name_buf = io.BytesIO(raw_bytes)
        name_buf.name = file_name
        fund_names = detect_fund_names_from_legacy(name_buf)

        # ── Sync FundDetailsConfig with current fund names ────────────────────
        config: FundDetailsConfig = st.session_state.fund_details_config
        config.sync_from_names(fund_names)

        # ── Sidebar: anchor window controls ──────────────────────────────────
        with st.sidebar:
            st.divider()
            st.subheader("Comparison Window")
            anchor_fund_options = ["(none)"] + fund_names
            anchor_fund_sel = st.selectbox(
                "Anchor fund",
                options=anchor_fund_options,
                help="Series start from this fund's earliest data year.",
            )
            override_year_input = st.number_input(
                "Override start year (optional)",
                min_value=1900,
                max_value=2100,
                value=0,
                step=1,
                help="Set to 0 to use the anchor fund's natural start year.",
            )

        anchor_window: AnchorWindow = st.session_state.anchor_window
        anchor_window.anchor_fund = None if anchor_fund_sel == "(none)" else anchor_fund_sel
        anchor_window.override_start_year = int(override_year_input) if override_year_input > 0 else None

        # ── Sidebar: benchmark selection ──────────────────────────────────────
        with st.sidebar:
            st.divider()
            st.subheader("Benchmark")
            benchmark_options = ["(auto / SPX)"] + fund_names
            benchmark_sel = st.selectbox(
                "Benchmark fund",
                options=benchmark_options,
                help="Select any loaded fund as benchmark. Defaults to SPX_Return column if present.",
            )
        benchmark_fund_arg = None if benchmark_sel == "(auto / SPX)" else benchmark_sel

        # ── Run analysis ──────────────────────────────────────────────────────
        legacy_buffer = io.BytesIO(raw_bytes)
        legacy_buffer.name = file_name
        legacy_result = build_legacy_analysis(
            legacy_buffer,
            risk_free_rate=risk_free,
            anchor_window=anchor_window,
            benchmark_fund=benchmark_fund_arg,
        )
        df = legacy_result["returns_df"]
        all_metrics = legacy_result["all_metrics"]
        benchmark_comparison_df = legacy_result["benchmark_comparison_df"]
        raw_data_df = legacy_result["raw_data_df"]
        legacy_assumptions = legacy_result["assumptions"]
        legacy_assumptions_df = legacy_result["assumptions_df"]
        has_benchmark = legacy_result["has_benchmark"]
        benchmark_name = legacy_result["benchmark_name"]
        export_file_name = "fund_legacy_report.xlsx"

        # Effective window info for UI
        esy = anchor_window.effective_start_year
        window_label = f" (window from {esy})" if esy else ""

        st.success(
            f"Detected legacy annual format. Loaded {legacy_result['row_count']} annual rows, "
            f"{legacy_result['fund_count']} fund(s){window_label}."
        )
        st.caption("Legacy annual uploads are analysed with annual metrics. Monthly scenario filters do not apply.")
        st.dataframe(df.head(20))

        # ── Fund Details configuration ────────────────────────────────────────
        with st.expander("⚙️ Fund Details Configuration (workbook Fund_Details parity)", expanded=False):
            st.caption(
                "Configure per-fund metadata. Changes persist in session state. "
                "Only included funds are shown in comparison tables."
            )

            # ── Bulk import from AI-extracted CSV ─────────────────────────────
            with st.expander("📥 Import Fund Details CSV", expanded=False):
                st.caption(
                    "Paste AI-extracted Fund Details CSV (columns: Fund, Strategy, ReturnType, "
                    "ManagementFee, PerformanceFee, HurdleRate, HWM, LiquidityNotes, SourceNote). "
                    "Use the AI Extraction Prompt Template above to generate this."
                )
                fd_paste = st.text_area(
                    "Paste Fund Details CSV",
                    height=120,
                    placeholder=(
                        "Fund,Strategy,ReturnType,ManagementFee,PerformanceFee,HurdleRate,HWM,LiquidityNotes,SourceNote\n"
                        "FundA,Equity Long/Short,Net,0.02,0.20,0.08,TRUE,Quarterly with 45-day notice,Q4 2023 Tear Sheet"
                    ),
                    key="fd_paste_area",
                )
                if st.button("Apply Fund Details CSV"):
                    try:
                        fd_df = pd.read_csv(io.StringIO(fd_paste.strip()))
                        col_map = {c.lower().replace(" ", "_"): c for c in fd_df.columns}
                        applied = 0
                        for _, row in fd_df.iterrows():
                            fname = str(row.get("Fund", row.get("fund", ""))).strip()
                            if not fname or fname not in fund_names:
                                continue
                            det: FundDetails = config.get(fname)
                            strategy_options = [
                                "Equity Long/Short", "Equity Long Only", "Fixed Income",
                                "Multi-Strategy", "Global Macro", "Event Driven",
                                "Real Assets", "Private Equity", "Other",
                            ]
                            raw_strategy = str(row.get("Strategy", row.get("strategy", det.strategy_type))).strip()
                            if raw_strategy in strategy_options:
                                det.strategy_type = raw_strategy
                            raw_rtype = str(row.get("ReturnType", row.get("returntype", det.return_type))).strip()
                            if raw_rtype in ("Gross", "Net"):
                                det.return_type = raw_rtype
                            for fee_field, det_attr in [
                                ("ManagementFee", "management_fee_pct"),
                                ("managementfee", "management_fee_pct"),
                                ("PerformanceFee", "performance_fee_pct"),
                                ("performancefee", "performance_fee_pct"),
                                ("HurdleRate", "hurdle_rate_pct"),
                                ("hurdlerate", "hurdle_rate_pct"),
                            ]:
                                if fee_field in row.index:
                                    try:
                                        val = float(row[fee_field])
                                        setattr(det, det_attr, val)
                                    except (TypeError, ValueError):
                                        pass
                            hwm_raw = str(row.get("HWM", row.get("hwm", ""))).strip().upper()
                            if hwm_raw in ("TRUE", "FALSE"):
                                det.high_water_mark = hwm_raw == "TRUE"
                            liq = str(row.get("LiquidityNotes", row.get("liquiditynotes", ""))).strip()
                            if liq and liq.lower() != "nan":
                                det.liquidity_notes = liq
                            src = str(row.get("SourceNote", row.get("sourcenote", ""))).strip()
                            if src and src.lower() != "nan":
                                det.source_note = src
                            config.set(det)
                            applied += 1
                        st.success(f"Applied fund details for {applied} fund(s). Scroll down to review.")
                    except Exception as e:
                        st.error(f"Could not parse Fund Details CSV: {e}")

            strategy_options = [
                "Equity Long/Short", "Equity Long Only", "Fixed Income",
                "Multi-Strategy", "Global Macro", "Event Driven",
                "Real Assets", "Private Equity", "Other",
            ]
            for fname in fund_names:
                det: FundDetails = config.get(fname)
                st.markdown(f"**{fname}**")
                cols = st.columns([1, 2, 1, 1, 2, 3])
                with cols[0]:
                    det.include = st.checkbox("Include", value=det.include, key=f"fd_include_{fname}")
                with cols[1]:
                    det.strategy_type = st.selectbox(
                        "Strategy",
                        options=strategy_options,
                        index=strategy_options.index(det.strategy_type),
                        key=f"fd_strategy_{fname}",
                    )
                with cols[2]:
                    det.return_type = st.selectbox(
                        "Return type",
                        options=["Gross", "Net"],
                        index=["Gross", "Net"].index(det.return_type),
                        key=f"fd_rtype_{fname}",
                    )
                with cols[3]:
                    det.high_water_mark = st.checkbox(
                        "HWM", value=det.high_water_mark, key=f"fd_hwm_{fname}"
                    )
                with cols[4]:
                    det.liquidity_notes = st.text_input(
                        "Liquidity notes",
                        value=det.liquidity_notes,
                        key=f"fd_liq_{fname}",
                        placeholder="Liquidity notes…",
                    )
                with cols[5]:
                    det.source_note = st.text_input(
                        "Source note",
                        value=det.source_note,
                        key=f"fd_src_{fname}",
                        placeholder="e.g. Q4 2023 Tear Sheet",
                    )
                config.set(det)

        included = config.included_funds() or list(all_metrics.keys())
        filtered_metrics = {f: v for f, v in all_metrics.items() if f in included}

        # ── Dashboard summary ─────────────────────────────────────────────────
        st.header("2. Dashboard Summary")
        summary = compute_dashboard_summary(all_metrics, included, benchmark_comparison_df)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Active Funds", summary["active_funds"])
        if summary["best_cagr_val"] is not None:
            c2.metric(
                "Best CAGR",
                f"{summary['best_cagr_val']:.1%}",
                delta=summary["best_cagr_fund"],
                delta_color="off",
            )
        if summary["best_sharpe_val"] is not None:
            c3.metric(
                "Best Sharpe",
                f"{summary['best_sharpe_val']:.2f}",
                delta=summary["best_sharpe_fund"],
                delta_color="off",
            )
        c4.metric("Meeting IPS Target", summary["count_ips_compliant"])
        if summary["has_benchmark"]:
            c5.metric("Beating Benchmark", summary["count_beating_benchmark"])

        # ── Wealth growth chart ────────────────────────────────────────────────
        st.subheader("Wealth Growth ($1M starting capital)")
        returns_wide_for_chart = legacy_result["returns_df"][
            [c for c in legacy_result["returns_df"].columns if c in included]
        ]
        benchmark_series_for_chart = None
        if has_benchmark and benchmark_name and benchmark_name not in included:
            bm_col = benchmark_name
            if bm_col in legacy_result["returns_df"].columns:
                benchmark_series_for_chart = legacy_result["returns_df"][bm_col].rename(bm_col)
        wealth_df = compute_wealth_growth(
            returns_wide_for_chart,
            benchmark_series=benchmark_series_for_chart,
        )
        wealth_long = wealth_df.reset_index().melt(id_vars="index", var_name="Fund", value_name="Value ($)")
        wealth_long = wealth_long.rename(columns={"index": "Year"})
        fig = px.line(
            wealth_long,
            x="Year",
            y="Value ($)",
            color="Fund",
            labels={"Value ($)": "Portfolio Value ($)", "Year": ""},
            template="simple_white",
        )
        fig.update_layout(legend_title_text="", hovermode="x unified")
        fig.update_yaxes(tickformat="$,.0f")
        st.plotly_chart(fig, use_container_width=True)

        # ── Annual Metrics ─────────────────────────────────────────────────────
        st.header("3. Annual Metrics")
        if not filtered_metrics:
            st.warning("No included funds found. Check Fund Details configuration above.")
        else:
            metrics_df = pd.DataFrame(filtered_metrics).T
            metrics_df.index.name = "Fund"
            metrics_df.columns = [c.replace("_", " ").title() for c in metrics_df.columns]

            def _color_ips_col(series: pd.Series) -> list[str]:
                return [
                    "background-color: #d4edda" if v is True else (
                        "background-color: #f8d7da" if v is False else ""
                    )
                    for v in series
                ]

            styler = metrics_df.style.format(
                {c: "{:.4f}" for c in metrics_df.select_dtypes("number").columns},
                na_rep="—",
            )
            if "Ips Compliant" in metrics_df.columns:
                styler = styler.apply(_color_ips_col, subset=["Ips Compliant"])
            st.dataframe(styler, use_container_width=True)

            if "Ips Compliant" in metrics_df.columns:
                ips_df = metrics_df[
                    [c for c in ["Cagr", "Ips Target", "Ips Delta", "Ips Compliant"] if c in metrics_df.columns]
                ].copy()
                st.subheader("IPS Compliance")
                ips_styler = ips_df.style.format(
                    {c: "{:.4f}" for c in ips_df.select_dtypes("number").columns},
                    na_rep="—",
                )
                if "Ips Compliant" in ips_df.columns:
                    ips_styler = ips_styler.apply(_color_ips_col, subset=["Ips Compliant"])
                st.dataframe(ips_styler, use_container_width=True)

        # ── Benchmark comparison ───────────────────────────────────────────────
        if has_benchmark and benchmark_comparison_df is not None and not benchmark_comparison_df.empty:
            bmark_label = benchmark_name or "benchmark"
            st.header(f"4. Fund vs {bmark_label}")
            display_df = benchmark_comparison_df.loc[
                benchmark_comparison_df.index.isin(included)
            ].copy()
            display_df.index.name = "Fund"
            display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]

            def _color_excess_col(series: pd.Series) -> list[str]:
                out = []
                for v in series:
                    try:
                        fv = float(v)
                        if fv > 0:
                            out.append("background-color: #d4edda")
                        elif fv < 0:
                            out.append("background-color: #f8d7da")
                        else:
                            out.append("")
                    except (TypeError, ValueError):
                        out.append("")
                return out

            bm_styler = display_df.style.format(
                {c: "{:.4f}" for c in display_df.select_dtypes("number").columns},
                na_rep="—",
            )
            for col in ["Excess Cagr", "Fund Ips Compliant"]:
                if col not in display_df.columns:
                    continue
                if col == "Excess Cagr":
                    bm_styler = bm_styler.apply(_color_excess_col, subset=[col])
                elif col == "Fund Ips Compliant":
                    bm_styler = bm_styler.apply(_color_ips_col, subset=[col])
            st.dataframe(bm_styler, use_container_width=True)
            st.caption(
                f"Annual comparison aligned to common window. "
                f"Benchmark: **{bmark_label}**. "
                "Green = beating benchmark / IPS-compliant; red = below."
            )

        # ── Assumptions ────────────────────────────────────────────────────────
        assumptions_header_num = "5" if has_benchmark else "4"
        st.header(f"{assumptions_header_num}. Assumptions & workbook parity notes")
        if legacy_assumptions_df is not None and not legacy_assumptions_df.empty:
            st.dataframe(legacy_assumptions_df, use_container_width=True)
            st.caption(
                "CPI (3.0%), IPS premium (6.0%), and risk-free (2.0%) are now confirmed "
                "from direct workbook inspection. Returns are treated as gross/pre-fee."
            )

        export_header_num = str(int(assumptions_header_num) + 1)

    else:
        # ── Monthly wide format ───────────────────────────────────────────────
        monthly_buffer = io.BytesIO(raw_bytes)
        monthly_buffer.name = file_name
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

        export_header_num = "5" if use_benchmark else "4"

    # ── Export ────────────────────────────────────────────────────────────────
    st.header(f"{export_header_num}. Export")

    excel_buf = io.BytesIO()
    if input_format == "legacy_annual":
        fund_details_list = st.session_state.fund_details_config.all_funds()
        export_legacy_report_to_excel(
            all_metrics,
            raw_data_df=raw_data_df if raw_data_df is not None else pd.DataFrame(),
            output=excel_buf,
            comparison_df=benchmark_comparison_df,
            assumptions=legacy_assumptions_df if legacy_assumptions_df is not None else legacy_assumptions,
            fund_details=fund_details_list if fund_details_list else None,
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
    st.info("Upload a CSV or Excel file, or paste CSV rows in the Paste tab to get started.")
    with st.expander("Expected file format"):
        st.markdown("""
**Monthly wide format:**

| date       | FundA | FundB | Benchmark |
|------------|-------|-------|-----------|
| 2020-01-31 | 0.012 | -0.005 | 0.008 |
| 2020-02-29 | -0.032| -0.081 | -0.040 |

**Legacy annual long format:**

| Fund      | Year | Fund_Return | SPX_Return | Months_In_Period |
|-----------|------|-------------|------------|------------------|
| FundA     | 2020 | 0.15        | 0.18       | 12               |
| FundA     | 2021 | 0.08        | 0.28       | 12               |

- Select any loaded fund column as **benchmark** — not limited to SPX
- Use the **Comparison Window** sidebar to anchor all funds to a common start year
- Configure per-fund metadata in the **Fund Details** expander
- Use the **AI Extraction Prompt Template** above to extract data from PDFs with Claude
        """)
