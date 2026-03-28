# Workbook Inventory & Parity Target Memo

**Date:** 2026-03-28  
**Status:** Based on direct inspection of legacy folder and MVP repo  
**Legacy path:** `/mnt/c/Users/sally/OneDrive/Fund Evaluation Tool/`  
**MVP repo:** `/home/sallylinux/.openclaw/workspace/repo/fund-evaluation-tool/`

---

## 1. Legacy File Inventory

| File | Type | Status |
|------|------|--------|
| `IPS_MultiFund_Model_v13.2.xlsm` | Active workbook | **Primary reference** |
| `IPS_MultiFund_Model_v13.1.xlsm` | Workbook | Prior version |
| `IPS_MultiFund_Model_v13.xlsm` | Workbook | Prior version |
| `IPS_MultiFund_Model_v12.1.xlsm` | Workbook | Older |
| `IPS_MultiFund_Model_v12.1-ss.xlsm` | Workbook | Snapshot variant |
| `IPS_MultiFund_Model_v11.xlsx` | No macros | Oldest inspectable |
| `IPS_MultiFund_Model_Spec_v1.docx` | Spec doc | Not inspected (binary) |
| `RebuildModule.bas` | Exported VBA | **Inspected** |
| `Fund input/FUND_DETAILS_SPY.csv` | Fund config | **Inspected** |
| `Fund input/HCI_Fund_Performance_Extract.csv` | Returns data | **Inspected** |
| `Fund input/RAW_DATA_SPY.csv` | Benchmark data | **Inspected** |
| `Fund tear sheet/*.pdf` | Source docs | 4 PDFs (not inspected) |

---

## 2. Legacy Workbook Sheet Structure (from handover doc + RebuildModule.bas)

The handover doc lists 14 sheets. The VBA module confirms actual sheet names differ slightly from the spec:

| Sheet Name (spec) | Sheet Name (VBA) | Purpose |
|---|---|---|
| Raw_Annual | `Raw_Data` | Annual returns, long format |
| Fund_Details | `Fund_Details` | Fund config & fee terms |
| Chart | `Wealth Growth` | Growth of $10M chart |
| — | `Chart_Helper` | Intermediate chart data |
| Inputs | Inputs | Global parameters |
| Fee_Engine | Fee_Engine | Fee waterfall |
| Calculations | Calculations | Performance metrics |
| Comparison | Comparison | Main results |
| Enhanced_Comparison | Enhanced_Comparison | Add-on results |
| Rolling_Analysis | Rolling_Analysis | 3Y/6Y rolling |
| Scenario_Results | Scenario_Results | Stress tests |
| Addon_Control | Addon_Control | Mode selector |
| Addon_Calculations | Addon_Calculations | Advanced metrics |
| Addon_Dashboard | Addon_Dashboard | Visual summary |

**Note:** Excel file internals cannot be read without Excel/COM access. Sheet layouts above are from handover doc + VBA inspection only.

---

## 3. Legacy Data Format (Confirmed by CSV Inspection)

### 3a. Fund Details CSV (11 columns)
```
Fund, Include?, Strategy_Type, Return_Type, Fee_Mode, Fee_Status,
Mgmt_Fee, Perf_Fee, Hurdle_Type, HWM, Liquidity_Notes
```

### 3b. Fund Performance Extract CSV (13 columns, long format)
```
Fund, Year, Fund_Return, SPX_Return, Is_Partial_Year, Months_In_Period,
Fee_Mode, Mgmt_Fee_%, Perf_Fee_%, Hurdle_Type, Hurdle_Value,
HWM_Enabled, Source_Notes
```
- Returns are decimal (0.365 = 36.5%)
- One row per fund per year
- SPX return included in same row (benchmark co-located)
- Partial year flagged with `Is_Partial_Year` + `Months_In_Period`

### 3c. Raw Data CSV (8 columns)
```
Fund, Frequency, Year, Month, Fund_Return, Is_Partial_Year,
Months_In_Period, Source_Notes
```
- SPY data stored separately, annual + monthly variants

---

## 4. MVP vs Legacy: Gap Analysis

### 4a. Data Model Mismatch (CRITICAL)

| | Legacy | MVP |
|---|---|---|
| Granularity | **Annual** (primary) | **Monthly** (required) |
| Format | **Long** (one row/fund/year) | **Wide** (one col/fund) |
| Benchmark | Embedded in returns row | Not present |
| Partial year | Explicit flag + months | Not handled |
| Fee terms | Stored with each row | Not present |

The MVP's `loader.py` and `app/main.py` assume monthly wide-format data. All legacy data is annual long-format. **This must be resolved first.**

### 4b. Metrics Gap

| Metric | Legacy | MVP |
|---|---|---|
| CAGR (with partial year) | ✅ | ❌ (uses monthly compounding only) |
| Arithmetic average | ✅ | ❌ |
| Ending value ($1M or $10M) | ✅ | ❌ |
| Annualised volatility | ✅ | ✅ (monthly) |
| Downside deviation | ✅ | ❌ |
| Sortino ratio | ✅ | ❌ |
| Sharpe ratio | ✅ | ✅ (monthly-based) |
| Max drawdown | ✅ | ✅ |
| Calmar ratio | ✅ | ✅ |
| IPS compliance (CAGR ≥ CPI+6%) | ✅ | ❌ |
| Benchmark comparison (vs SPX) | ✅ | ❌ |
| Fee engine (any mode) | ✅ | ❌ |

### 4c. Export Gap

| | Legacy | MVP |
|---|---|---|
| Sheets | 14 structured sheets | 1 flat Metrics sheet |
| Formatting | Conditional formatting, colour-coding | None |
| Growth chart | $10M wealth growth line chart | None |
| IPS compliance display | Green/red indicators | None |

---

## 5. Recommended First Parity Targets (Priority Order)

### Priority 1 — Data model alignment
**What:** Make the loader accept the legacy CSV format (annual long-format with SPX column and partial-year fields).  
**Why:** Nothing else works until the data can be ingested. All test data is in this format.  
**Acceptance:** `load_fund_data()` returns a DataFrame that preserves fund name, year, fund return, SPX return, partial-year flag, and months in period.

### Priority 2 — Annual CAGR with partial-year handling
**What:** Implement CAGR calculation using annual returns + partial-year metadata.  
**Formula:** `CAGR = (∏(1 + rᵢ))^(1/T) - 1` where T = sum of (months/12) for each period.  
**Why:** All downstream metrics and IPS compliance depend on correct CAGR. This is the most frequently cited output.  
**Acceptance:** CAGR for HCI (1998–2025 partial) matches expected value from tear sheet within ±0.01%.

### Priority 3 — SPX benchmark comparison
**What:** Accept SPX_Return alongside fund return and compute same metrics for both.  
**Why:** Every output in the Comparison sheet is fund-vs-SPX. Parity requires benchmark column.  
**Acceptance:** CAGR, Sharpe, and max drawdown computed for both fund and SPX from the same date range.

### Priority 4 — Sortino ratio + downside deviation
**What:** Add downside deviation (MAR=0, using annual returns below zero) and Sortino = (CAGR - rf) / downside deviation.  
**Why:** Legacy lists Sortino as a core metric alongside Sharpe. Currently missing.  
**Acceptance:** Sortino for HCI matches manual calculation from annual returns.

### Priority 5 — IPS compliance flag
**What:** Flag whether fund CAGR ≥ (CPI + 6%), using configurable CPI assumption from settings.  
**Why:** The entire tool is framed as IPS compliance analysis. This is the headline output.  
**Acceptance:** Compliance boolean + CAGR vs target delta displayed per fund.

### Priority 6 — Excel export multi-sheet structure
**What:** Replace single-sheet export with at minimum: (1) Summary/Comparison sheet, (2) Raw data sheet.  
**Why:** The legacy output is a multi-sheet workbook. Single-sheet export is not usable for IPS reporting.  
**Acceptance:** Download produces workbook with Comparison sheet showing fund vs SPX side-by-side.

---

## 6. Defer to Later

The following legacy features are confirmed present but should **not** block MVP parity:
- Fee engine (all 3 modes) — complex, data not yet structured for it
- Rolling 3Y/6Y analysis — requires sufficient history
- Add-on metrics (16 optional) — Phase 2
- Monte Carlo / scenario stress tests — Phase 2
- Chart automation — Phase 2
- AI PDF extraction prompt — Phase 2

---

## 7. Open Questions

These could not be resolved without opening the `.xlsm` files directly:

- [ ] Default risk-free rate in the Inputs sheet (assumed 4% in MVP)
- [ ] Default CPI assumption for IPS target (CPI+6%)
- [ ] Exact management fee accrual basis (beginning NAV? ending? average?)
- [ ] HWM reset logic: calendar year end, or rolling?
- [ ] Exact SPX series used: WHT-adjusted, total return, or price return?
- [ ] Whether arithmetic average uses geometric weighting for partial years

**Recommendation:** Open `v13.2.xlsm` in Excel, navigate to the Inputs sheet, and document all parameter defaults. This would resolve all open questions above in a single session.
