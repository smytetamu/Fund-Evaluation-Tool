# Workbook Inventory Plan

## Purpose

Before implementing the Python fee engine and metrics, the legacy Excel workbooks must be inspected systematically to:
1. Extract ground-truth calculation logic
2. Identify edge cases and parameter combinations actually in use
3. Generate test fixtures (input → expected output) for the Python engine

This document defines the inventory process. It does **not** claim the workbooks have been inspected yet — that work is pending.

## Known Legacy Files

Location: `/mnt/c/Users/sally/OneDrive/Fund Evaluation Tool/`

| File | Notes |
|------|-------|
| `IPS_MultiFund_Model_v13.2.xlsm` | Latest version — primary reference |
| `IPS_MultiFund_Model_v13.1.xlsm` | One version prior |
| `IPS_MultiFund_Model_v13.xlsm` | |
| `IPS_MultiFund_Model_v12.1.xlsm` | |
| `IPS_MultiFund_Model_v12.1-ss.xlsm` | Possibly a "snapshot" variant |
| `IPS_MultiFund_Model_v11.xlsx` | Older format, no macros |
| `IPS_MultiFund_Model_Spec_v1.docx` | Specification document — inspect first |
| `RebuildModule.bas` | Exported VBA module — readable without Excel |
| `Fund input/` | Directory — likely CSV or Excel fund input files |
| `Fund tear sheet/` | Directory — likely PDF or Excel fund tear sheets |

## Inspection Priority

### Step 1 — Read the spec doc and VBA module (no Excel required)
- `IPS_MultiFund_Model_Spec_v1.docx` — extract fee logic rules, metric definitions
- `RebuildModule.bas` — extract VBA fee waterfall, metric formulas

**Deliverable:** Annotated copy of the VBA fee engine and a list of all supported parameters.

### Step 2 — Inspect `v13.2.xlsm` sheet structure
For each of the 14 known sheets, document:
- Column layout and data types
- Named ranges used
- Formula logic (especially Fee_Engine and Calculations sheets)
- Conditional formatting rules (IPS compliance logic)

**Sheets to inspect in priority order:**
1. `Fee_Engine` — core fee waterfall formulas
2. `Calculations` — performance metric formulas
3. `Comparison` — final output layout (informs Excel export format)
4. `Fund_Details` — fee term configuration (informs data model)
5. `Raw_Annual` — input format (informs data entry UI)
6. `Inputs` — global parameters
7. `Scenario_Results` — for Phase 2 reference only

### Step 3 — Extract test fixtures
From `v13.2.xlsm` (or `Fund input/` CSVs if available), extract at least:
- 1 fund with `net_provided` fee mode
- 1 fund with `apply_literature` + hard hurdle + HWM
- 1 fund with `apply_literature` + soft hurdle
- 1 fund with `apply_literature` + catch-up provision
- 1 fund with partial year data

For each: record raw returns, fee parameters, expected net returns, expected CAGR/Sharpe/drawdown.

**Deliverable:** `tests/fixtures/legacy_cases.json` with these cases.

### Step 4 — Review `Fund input/` and `Fund tear sheet/` directories
- Identify what real fund data is stored here
- Determine if any can be used as anonymised test data
- Note CSV format expected by the legacy import tool

## Known Logic (from handover doc — pre-inspection)

The following is extracted from `project-handover-doc.md` and is considered reliable but should be validated against the actual workbook formulas:

### Fee Waterfall (10 steps)
1. Start with Prior NAV (or $10M initial)
2. Apply gross return → gross NAV
3. Calculate management fee (accrual frequency: monthly/quarterly/annual)
4. Apply management fee → NAV after mgmt
5. Determine hurdle amount (by hurdle type and terms)
6. Calculate excess over hurdle/HWM
7. Apply performance fee logic:
   - Hard hurdle: fee only on excess above hurdle
   - Soft hurdle: fee on total return if hurdle is met
   - Catch-up: manager receives catch-up % until even, then splits
8. Apply other fees → final NAV
9. Update high-water mark
10. Generate audit trail

### Performance Metrics
| Metric | Notes |
|--------|-------|
| CAGR | Partial-year handling required |
| Arithmetic average | Simple mean of annual returns |
| Ending value | From $1M base |
| Volatility | Annualised std dev |
| Downside deviation | Returns below 0 (MAR=0) |
| Max drawdown | Peak-to-trough on cumulative NAV |
| Sharpe ratio | (CAGR - risk-free) / volatility |
| Sortino ratio | (CAGR - risk-free) / downside deviation |
| Calmar ratio | CAGR / |max drawdown| |
| IPS compliance | CAGR ≥ CPI+6%; drawdown within threshold |

*Note: Risk-free rate and CPI assumptions are configurable parameters from the Inputs sheet. Inspect `v13.2.xlsm` to confirm defaults.*

## Validation Approach

Once the Python engine is built:
1. Load each test fixture into the Python engine
2. Assert outputs match legacy expected values within a tolerance of ±0.01% for returns and ±0.001 for ratios
3. Any discrepancy triggers investigation of formula differences before declaring parity

## Open Questions (to resolve during inspection)

- [ ] What is the default risk-free rate used in Sharpe/Sortino?
- [ ] What CPI assumption drives the IPS target (CPI+6%)?
- [ ] How exactly is annualisation handled for partial first/last years in CAGR?
- [ ] What is the HWM reset logic in detail (calendar year vs rolling)?
- [ ] Are management fees deducted on beginning NAV, ending NAV, or average?
- [ ] What's in `Fund input/` and `Fund tear sheet/` directories?
