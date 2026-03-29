# Parity Metric Specification — Next Implementation Slice

**Date:** 2026-03-29  
**Author:** EE (analysis agent)  
**Basis:** `workbook-parity-memo.md` + inspection of `src/fund_evaluation_tool/metrics/calculator.py`  
**Status:** Ready for implementation handoff

---

## 1. Metrics to Add (Exact Definitions)

These are the gaps identified in the parity memo that the current `calculator.py` does not cover.

### 1a. Annual CAGR with Partial-Year Handling

**Function signature:** `compute_cagr(annual_returns: pd.Series, months_per_period: pd.Series) -> float`

**Formula:**
```
T = sum(months_per_period) / 12           # total years, may be fractional
gross = prod(1 + r_i for r_i in annual_returns)
CAGR = gross^(1/T) - 1
```

**Notes:**
- `annual_returns` is a Series of decimal annual returns (e.g. 0.12 for 12%).
- `months_per_period` is a parallel Series of integers (1–12); full-year rows = 12.
- T is the exact fractional years elapsed, not simply the row count.
- If T == 0 or gross <= 0, return `nan`.

---

### 1b. Arithmetic Average Return

**Formula:** `mean(annual_returns)` (simple mean, no partial-year weighting)

**Note:** Legacy reports both arithmetic and geometric (CAGR). Both should be computed and returned.

**OPEN QUESTION:** Whether partial years should be included or excluded from the arithmetic average. Legacy behaviour unknown without opening the workbook. **Default:** include all rows, flag as assumption.

---

### 1c. Ending Value

**Formula:** `starting_value * prod(1 + r_i for r_i in annual_returns)`

- `starting_value` is a configurable parameter (legacy uses $10M; MVP can default to $1M or accept as argument).
- Partial-year rows are included at face value (no prorating of the return — the return is already the actual return for that period).

---

### 1d. Downside Deviation

**Function signature:** `compute_downside_deviation(annual_returns: pd.Series, mar: float = 0.0) -> float`

**Formula:**
```
shortfalls = min(r_i - mar, 0) for each r_i
downside_dev = sqrt(mean(shortfalls^2))
```

- MAR (minimum acceptable return) defaults to 0.
- This is the **population-style** formula (divide by N, not N-1), consistent with standard Sortino convention.
- **OPEN QUESTION:** Legacy MAR value (0%, hurdle rate, or risk-free rate). Default: 0% until confirmed.
- Only strictly-negative deviations contribute (i.e. returns above MAR are zeroed, not truncated to MAR).

---

### 1e. Sortino Ratio

**Function signature:** `compute_sortino(cagr: float, downside_dev: float, risk_free_rate: float = 0.0) -> float`

**Formula:**
```
Sortino = (CAGR - risk_free_rate) / downside_deviation
```

- Returns `nan` if `downside_deviation == 0`.
- Uses the annual CAGR (with partial-year handling), not arithmetic mean.
- `risk_free_rate` is annualised; default 0.0 (can be overridden globally).

---

### 1f. SPX Benchmark Metrics

**Requirement:** Compute the same metric set (CAGR, arithmetic mean, vol, Sharpe, Sortino, max drawdown, Calmar) for the SPX return series in parallel with the fund series.

**Data source:** `SPX_Return` column in the legacy long-format CSV (already co-located with fund returns in `HCI_Fund_Performance_Extract.csv`).

**Output structure:** All benchmark metrics should use the same keys prefixed with `benchmark_` (e.g. `benchmark_cagr`, `benchmark_sharpe`) to allow side-by-side comparison.

**Alignment rule:** Fund and benchmark metrics must be computed over **identical date ranges**. If SPX is missing for a given year, that year must be excluded from both series. Log a warning if rows are dropped.

---

### 1g. IPS Compliance Flag

**Function signature:** `compute_ips_compliance(cagr: float, cpi: float, target_spread: float = 0.06) -> dict`

**Formula:**
```
ips_target = cpi + target_spread   # e.g. 0.03 + 0.06 = 0.09
compliant = cagr >= ips_target
delta = cagr - ips_target          # positive = outperformance
```

**Returns:** `{"ips_target": float, "compliant": bool, "delta": float}`

**OPEN QUESTIONS (placeholders — must be confirmed before implementation):**
- [ ] Default CPI assumption (parity memo suggests CPI+6%; actual CPI value unknown — assume 3.0% until confirmed from workbook Inputs sheet).
- [ ] Whether compliance is evaluated on net-of-fee or gross CAGR (assume net-of-fee once fee engine exists; gross for now).
- [ ] Whether the IPS target is per-fund or a single global setting (assume global for MVP).
- [ ] Time horizon for compliance check (full history CAGR, or only past N years — assume full history).

---

## 2. Annual-Data Assumptions

The current `calculator.py` assumes **monthly** data (`ANN_FACTOR = 12`). The legacy data is **annual**.

For the new functions above:
- Input series are **annual** (one value per year).
- Volatility from annual returns = `stdev(annual_returns)` directly (no sqrt(12) scaling).
- Sharpe from annual returns = `(mean_annual_return - risk_free_rate) / std_annual_returns` (using arithmetic mean for legacy Sharpe consistency — **OPEN QUESTION**: legacy likely uses arithmetic mean for Sharpe numerator, not CAGR).
- Do not mix annual and monthly data paths without explicit conversion.

The existing monthly `compute_metrics()` function should remain untouched; the new functions form a separate `annual_metrics` module or are added as clearly-named parallel functions.

---

## 3. Partial-Year Handling Options

Three approaches, evaluated:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A. Exact fractional T | Sum months/12 for T; compound all returns | Mathematically correct; matches standard CAGR convention | Requires `months_per_period` Series |
| B. Exclude partial years | Drop rows where `months < 12` before computing CAGR | Simple; conservative | Loses data; distorts inception-to-date calc |
| C. Pro-rate partial return | Scale partial-year return to annual before compounding | Intuitive but wrong — compounds a scaled return | Distorts terminal value |

**Recommended default: Option A (exact fractional T).**

- Rationale: The legacy CSV already carries `Months_In_Period` for every row, making Option A trivially implementable. Options B and C lose information or introduce mathematical error.
- For **volatility** and **downside deviation** calculations, partial-year rows should be **included as-is** (do not pro-rate; they represent real observed returns for that period).
- For **arithmetic average**, include partial years (flag as assumption — see §1b open question).

---

## 4. IPS Flag — Definition Placeholders & Unknowns

Current state: IPS compliance logic is fully absent from the MVP codebase.

**What is known:**
- Target is CAGR ≥ CPI + 6% (from parity memo, sourced from legacy handover doc).
- The fund in scope is HCI; legacy workbook shows green/red compliance indicators.
- There is a `Inputs` sheet in the workbook that presumably stores CPI and risk-free rate.

**Placeholders to use until workbook is opened:**

| Parameter | Placeholder Value | Source |
|-----------|------------------|--------|
| CPI assumption | 3.0% (0.03) | Common US historical average; not confirmed from workbook |
| Target spread | 6.0% (0.06) | Stated in parity memo |
| Risk-free rate | 4.0% (0.04) | Already used in MVP |
| Net vs gross | Gross (pre-fee) | Fee engine not yet implemented |

**Action required before final implementation:** Open `IPS_MultiFund_Model_v13.2.xlsm`, navigate to `Inputs` sheet, and record actual parameter defaults.

---

## 5. Benchmark Comparison Requirements for Legacy Parity

The legacy `Comparison` sheet shows fund metrics and SPX metrics side-by-side for the same date range.

**Minimum requirements for legacy parity:**

1. **Data alignment:** SPX returns must be sourced from the `SPX_Return` column already present in the legacy performance CSV. No external data fetch required for initial parity.

2. **Metric parity:** Every metric computed for the fund must also be computed for SPX:
   - CAGR (with partial-year handling, same T)
   - Arithmetic average return
   - Annualised volatility (from annual returns)
   - Sharpe ratio
   - Sortino ratio
   - Max drawdown
   - Calmar ratio
   - Ending value (same starting_value)

3. **Excess return:** Add `excess_cagr = fund_cagr - benchmark_cagr` as a derived metric.

4. **Relative Sharpe / Information Ratio:** Out of scope for this slice (defer to Phase 2).

5. **Output structure:** The `compute_metrics()` return dict (or equivalent annual version) should support a `benchmark=True` flag or a separate `compute_benchmark_metrics()` wrapper that prefixes all keys.

6. **Display requirement (app layer):** The Streamlit UI should show a two-column comparison table: Fund | SPX. This is a UI task separate from the metric implementation.

---

## 6. Implementation Order (Recommended)

1. `compute_cagr(annual_returns, months_per_period)` — unblocks everything downstream
2. `compute_downside_deviation(annual_returns, mar=0.0)`
3. `compute_sortino(cagr, downside_dev, rf=0.0)`
4. `compute_ips_compliance(cagr, cpi, spread=0.06)`
5. Benchmark parallel computation (reuse functions, pass SPX series)
6. Wire into a single `compute_annual_metrics(fund_series, spx_series, months_series, ...)` entry point

---

## 7. Unresolved Questions Summary

| # | Question | Impact | Blocked on |
|---|----------|--------|-----------|
| 1 | Default CPI in workbook Inputs sheet | IPS compliance target | Opening v13.2.xlsm |
| 2 | Default risk-free rate in workbook | Sharpe, Sortino numerator | Opening v13.2.xlsm |
| 3 | MAR for downside deviation (0%, hurdle, or rf?) | Sortino value | Opening v13.2.xlsm |
| 4 | Sharpe numerator: arithmetic mean or CAGR? | Sharpe value | Opening v13.2.xlsm |
| 5 | Arithmetic average: include or exclude partial years? | Arithmetic average | Opening v13.2.xlsm |
| 6 | IPS compliance: net-of-fee or gross CAGR? | Compliance flag | Fee engine implementation |
| 7 | IPS target: global or per-fund? | Data model | Opening v13.2.xlsm |
| 8 | SPX series: price return, total return, or WHT-adjusted? | Benchmark accuracy | Opening v13.2.xlsm |

All items 1–5 and 7–8 can be resolved in a single session with the workbook open in Excel.
