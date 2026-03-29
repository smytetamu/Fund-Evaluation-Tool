# Next Demo Priority — Post Parity Metric Slice

**Date:** 2026-03-29  
**Author:** EE (review agent)  
**Status:** Recommendation — review/doc only

---

## Current State (after parity metric slice)

| Layer | Status |
|-------|--------|
| Monthly metrics (Sharpe, Calmar, vol, drawdown) | ✅ Implemented + 16 tests |
| Benchmark comparison (monthly) | ✅ Implemented |
| Legacy annual loader (`load_legacy_annual`) | ✅ Implemented + tests |
| Parity metric spec (`parity-metric-spec.md`) | ✅ Written, ready for implementation |
| Annual metrics module (`compute_annual_metrics`) | ❌ Spec written, not implemented |
| Legacy CSV wired into Streamlit UI | ❌ Not wired |
| Fund vs SPX side-by-side in the app | ❌ Not visible |

The spec is fully written (§1–§6 of `parity-metric-spec.md`). The loader can already parse the legacy CSV and extract the SPX series. The gap is that none of this is callable from the UI — a user cannot yet upload the real HCI fund file and see the comparison.

---

## #1 Recommendation: Wire the Legacy Loader + Annual Metrics into the Streamlit UI

### What to build (minimum change)

1. **`src/fund_evaluation_tool/metrics/annual_calculator.py`** — implement the five functions already specified:
   - `compute_cagr(annual_returns, months_per_period)`
   - `compute_downside_deviation(annual_returns, mar=0.0)`
   - `compute_sortino(cagr, downside_dev, rf=0.0)`
   - `compute_ips_compliance(cagr, cpi=0.03, spread=0.06)`
   - `compute_annual_metrics(fund_series, spx_series, months_series, rf=0.04)` — entry point

2. **`app/main.py`** — add a second upload path: detect legacy long format (by column names), call `load_legacy_annual`, compute annual metrics for each fund + SPX, render a two-column Fund | SPX comparison table, show IPS compliance flag (green/red).

3. **No schema migration, no DB work, no fee engine** — out of scope for this slice.

### Why this is the strongest single demo improvement

The current demo proves you can load a CSV and get numbers. The next demo question from any stakeholder will be: **"Can it replicate what the workbook shows?"**

The workbook shows:
- HCI CAGR vs SPX CAGR, side by side
- IPS compliance (green/red against CPI+6% target)
- Annual returns table

All three are achievable with this single slice:
- The loader already parses the legacy CSV and extracts SPX.
- The spec defines all the math.
- The UI change is ~40 lines.

This is the minimum increment that turns the demo from "metrics tool" to "workbook replacement proof of concept" — the core buy-in moment.

### Estimated effort

- `annual_calculator.py`: ~60 lines + ~20 lines of tests
- `app/main.py` wiring: ~40 lines
- Total: ~2–3 hours for implementation + tests

### Assumptions / open items (from parity spec)

The following placeholders are used until workbook `Inputs` sheet is opened:

| Parameter | Placeholder | Flag |
|-----------|-------------|------|
| CPI | 3.0% | Assumption — hardcoded in IPS flag |
| MAR (Sortino) | 0.0% | Assumption |
| Sharpe numerator | Arithmetic mean | Assumption (legacy likely matches) |
| IPS scope | Gross CAGR | Assumption (no fee engine yet) |

These do not block the demo — the app can surface a visible "⚠️ Placeholder assumptions" banner.

### What to defer

- Fee engine (gross vs net of fee)
- Scenario filtering on annual data
- DB persistence
- Relative Sharpe / Information Ratio (monthly already covers this)
- Opening the v13.2 workbook to resolve the 8 open questions in the spec

---

## Handoff Note for Eddie

If this is delegated to the coder agent, the exact function signatures and formulas are in `docs/parity-metric-spec.md` §1 and §6. The legacy CSV schema is in `src/fund_evaluation_tool/ingestion/legacy_loader.py`. The monthly metrics pattern to follow is in `src/fund_evaluation_tool/metrics/calculator.py`. Do not modify `calculator.py` — add `annual_calculator.py` as a sibling.
