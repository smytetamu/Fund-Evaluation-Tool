# MVP Scope

## Included in MVP

### Data Entry & Management
- Add/edit/delete funds with name and metadata
- Enter annual return data per fund (year, return %, partial-year flag)
- Enter SPX benchmark returns
- Configure fund fee terms: mode, management fee %, performance fee %, hurdle type, HWM settings

### Fee Calculation Engine
Three fee modes (matching legacy):
1. **Net Provided** — use returns as-is, skip fee engine
2. **Apply Literature Terms** — full fee waterfall: management fee → hurdle → performance fee → HWM update
3. **Gross — Fees Not Applied** — flag for manual review, no calculation

Supported hurdle types: Fixed rate, CPI+X, Benchmark-relative, Absolute return  
Supported HWM: enabled/disabled, reset rules  
Supported performance fee logic: Hard hurdle, Soft hurdle, Catch-up

### Performance Metrics
- CAGR (with partial-year handling)
- Arithmetic average return
- Ending value (from $1M base)
- Volatility (annualised standard deviation)
- Downside deviation
- Maximum drawdown + recovery period
- Sharpe ratio
- Sortino ratio
- Calmar ratio
- IPS target compliance: CPI+6% hurdle, risk thresholds

### Comparison View
- Side-by-side fund table with all metrics
- Conditional formatting (pass/fail vs IPS targets)
- Benchmark column (SPX)
- Anchoring: align funds to common start date

### Export
- Excel export of the comparison table (openpyxl)
- Basic formatting: headers, number formats, conditional colour coding

## Excluded from MVP (Phase 2)

- Rolling CAGR analysis (3Y / 6Y)
- Capture ratios (upside/downside)
- CVaR / tail risk
- Recovery analytics
- Information ratio, batting average
- Inflation scenario testing
- Sequence of returns risk
- Consistency score
- Monte Carlo simulation
- PDF/PowerPoint export
- User authentication
- Multi-project management

## Scope Decisions

| Decision | Rationale |
|----------|-----------|
| Annual data only (no monthly) | Reduces complexity; monthly improves Sortino but is optional in legacy too |
| SQLite for persistence | Zero-infrastructure, sufficient for MVP scale |
| Streamlit for UI | Fast iteration, no frontend build tooling required |
| No live benchmark feeds | SPX entered manually, same as legacy |
| Excel export via openpyxl | Matches existing team workflow and expectations |
