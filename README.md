# Fund-Evaluation-Tool

A Streamlit-based MVP for evaluating and comparing investment funds.

## Overview

This tool allows users to:
- ingest fund data from CSV/Excel files
- calculate metrics (returns, volatility, Sharpe ratio, drawdown, benchmark comparison, etc.)
- run basic scenario filters
- export results to Excel reports
- support both MVP monthly inputs and legacy annual long-format inputs

## Quickstart

```bash
uv venv
uv pip install -e '.[dev]'
uv run streamlit run app/main.py
```

The app opens at http://localhost:8501.

## What it does

1. Upload a CSV or Excel file with fund returns
2. Auto-detect monthly wide vs legacy annual long format uploads
3. Compute the matching metric set automatically
4. Filter by scenario window where supported for monthly uploads
5. Display formatted fund metrics and benchmark/SPX comparison tables
6. Export results to Excel

## Accepted input shapes

### Monthly wide format

```csv
date,Fund_A,Fund_B,Fund_C
2020-01-31,0.012,-0.005,0.003
2020-02-29,-0.034,0.008,-0.012
```

- `date` is required
- each additional column is one fund
- values are decimal returns (`0.01 = 1%`)

### Legacy annual long format

```csv
Fund,Year,Fund_Return,SPX_Return,Is_Partial_Year,Months_In_Period
HCI,2021,0.223,0.287,0,12
HCI,2022,-0.108,-0.182,0,12
HCI,2023,0.154,0.265,1,9
```

Supported columns:
- `Fund` required
- `Year` required
- `Fund_Return` required
- `SPX_Return` optional
- `Is_Partial_Year` optional
- `Months_In_Period` optional

The Streamlit UI now auto-detects this schema by column names, routes it through the legacy loader, computes annual metrics per fund, surfaces IPS compliance, and shows a dedicated fund-vs-SPX comparison table when `SPX_Return` is present.

Fixtures:
- `tests/fixtures/sample_returns.csv`
- `tests/fixtures/legacy_annual_returns.csv`

## Metrics available

### Monthly return series (`compute_metrics`)

- total return
- annualised return
- annualised volatility
- Sharpe ratio
- max drawdown
- Calmar ratio
- number of periods

### Annual return series (`compute_annual_metrics`)

- CAGR
- arithmetic mean return
- annual volatility
- Sharpe ratio
- downside deviation
- Sortino ratio
- max drawdown
- Calmar ratio
- ending value
- IPS target
- IPS compliance
- IPS delta
- benchmark-prefixed comparison metrics via aligned annual series
- partial-year aware annual CAGR utilities

Defaults currently assumed in annual calculations:
- MAR = 0.0
- CPI = 3.0%
- target spread = 6.0%
- risk-free rate = 0.0

These defaults must be confirmed against the workbook Inputs sheet before being treated as production values.

## Benchmark comparison metrics

When a benchmark column is selected, the app computes:
- benchmark annualised return
- excess return
- tracking error
- information ratio
- beta
- alpha
- correlation

## Stack

- Python 3.11+
- Streamlit
- Pandas / NumPy
- openpyxl
- SQLite via SQLAlchemy

## Project structure

```text
app/
  main.py
src/fund_evaluation_tool/
  benchmark/
  db/
  export/
  ingestion/
  metrics/
  scenarios/
tests/
  fixtures/
docs/
```

## Running tests

```bash
uv run pytest -q
```

## Status

MVP — work in progress.
