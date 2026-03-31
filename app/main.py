"""Fund Evaluation Tool — Streamlit entrypoint."""

from __future__ import annotations

import io

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
from fund_evaluation_tool.metrics import compute_metrics
from fund_evaluation_tool.scenarios import run_scenario

st.set_page_config(page_title="Fund Evaluation Tool", layout="wide")
st.title("📊 Fund Evaluation Tool")

# ── Session state initialisation ─────────────────────────────────────────────
if "fund_details_config" not in st.session_state:
    st.session_state.fund_details_config = FundDetailsConfig()
if "anchor_window" not in st.session_state:
    st.session_state.anchor_window = AnchorWindow()

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

# ── Upload ────────────────────────────────────────────────────────────────────
st.header("1. Upload Fund Data")
st.caption(
    "CSV with a `date` column + one numeric column per fund (monthly returns as decimals, e.g. 0.01 = 1%)."
    " Or upload legacy annual format (columns: `Fund`, `Year`, `Fund_Return`)."
)
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
    legacy_assumptions_df = None
    export_file_name = "fund_report.xlsx"

    if input_format == "legacy_annual":
        # ── Detect fund names for sidebar controls ────────────────────────────
        name_buf = io.BytesIO(uploaded_bytes)
        name_buf.name = uploaded.name
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
        legacy_buffer = io.BytesIO(uploaded_bytes)
        legacy_buffer.name = uploaded.name
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
            strategy_options = [
                "Equity Long/Short", "Equity Long Only", "Fixed Income",
                "Multi-Strategy", "Global Macro", "Event Driven",
                "Real Assets", "Private Equity", "Other",
            ]
            for fname in fund_names:
                det: FundDetails = config.get(fname)
                st.markdown(f"**{fname}**")
                cols = st.columns([1, 2, 1, 1, 3])
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

        export_header_num = "5" if use_benchmark else "4"

    # ── Export ────────────────────────────────────────────────────────────────
    st.header(f"{export_header_num}. Export")

    excel_buf = io.BytesIO()
    if input_format == "legacy_annual":
        export_legacy_report_to_excel(
            all_metrics,
            raw_data_df=raw_data_df if raw_data_df is not None else pd.DataFrame(),
            output=excel_buf,
            comparison_df=benchmark_comparison_df,
            assumptions=legacy_assumptions_df if legacy_assumptions_df is not None else legacy_assumptions,
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
        """)
