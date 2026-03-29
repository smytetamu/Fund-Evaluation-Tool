# Next Step After Legacy UI Wiring

**Date:** 2026-03-30  
**Author:** EE (review only)

## Repo state reviewed

Confirmed in the current repo:
- `load_legacy_annual()` exists and is tested (`tests/test_legacy_loader.py`)
- annual metrics exist and are tested (`src/fund_evaluation_tool/metrics/annual_calculator.py`, `tests/test_annual_metrics.py`)
- the current Streamlit app (`app/main.py`) is still monthly-first and exports a generic metrics sheet plus optional monthly benchmark sheet
- Excel export is still generic (`src/fund_evaluation_tool/export/excel.py`): it writes `Metrics` and optional `Benchmark Comparison`, but not a legacy-style comparison/report package
- test suite passes: `89 passed`

## Ranked recommendation

### #1 — Build legacy-aware Excel/report export

After legacy CSV + annual metrics are wired into the UI, the next highest-value implementation step should be:

**Add a legacy annual report export path that produces a workbook-oriented output for fund vs SPX comparison, IPS result, and supporting raw data.**

## Why this is the best next step

1. **It closes the workflow, not just the screen demo.**  
   Once the UI can display annual legacy results, the next stakeholder question is usually not "can it render?" but "can I download the report I need?"

2. **The current export path is mismatched to the legacy use case.**  
   `export_to_excel()` currently assumes a generic metrics dict and optional monthly benchmark DataFrame. That is fine for the monthly MVP, but it does not represent the legacy output shape the docs describe.

3. **The docs already point here.**  
   `docs/workbook-parity-memo.md` lists **Excel export multi-sheet structure** as the next parity target after ingestion/metrics/comparison work. The repo now already has those earlier pieces in place.

4. **It leverages existing code instead of opening a new hard problem.**  
   The annual loader and annual metrics engine already exist. Export/report formatting is the strongest follow-on that turns those pieces into something usable without first needing fee-engine parity.

## Minimum slice

Implement a legacy export mode that writes at least:
- **Comparison** sheet — fund metrics side by side with SPX metrics and IPS pass/fail
- **Raw Data** sheet — annual input rows used for the calculation
- optionally an **Assumptions** sheet — CPI / risk-free / MAR placeholders currently used in annual calculations

## Explicitly not my top next step

### Fee engine parity
Still important, but not the best immediate follow-on **after** legacy UI wiring because:
- it is materially larger
- workbook-validation details are still unresolved in docs
- it does not create as fast a user-visible completion of the current annual legacy path as report export does

## Handoff note

If handed to Eddie, the implementation should likely start by:
- extending `src/fund_evaluation_tool/export/excel.py` for an annual/legacy export shape
- defining a small annual report payload instead of overloading the monthly `metrics: dict[str, dict]` structure
- wiring the new export branch from `app/main.py` only when the uploaded file is detected as legacy annual format
