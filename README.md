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
2. Compute core performance metrics automatically
3. Filter by scenario window where supported
4. Display results in formatted tables
5. Select a benchmark column for comparison metrics when desired
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

Supported columns:
- `Fund` required
- `Year` required
- `Fund_Return` required
- `SPX_Return` optional
- `Is_Partial_Year` optional
- `Months_In_Period` optional

A realistic legacy fixture is at:
- `tests/fixtures/legacy_annual_returns.csv`

A sample monthly file is at:
- `tests/fixtures/sample_returns.csv`

## Metrics available

Current repo includes support for:
- total return
- annualised return / CAGR
- annualised volatility
- Sharpe ratio
- max drawdown
- Calmar ratio
- downside deviation
- Sortino ratio
- benchmark-relative comparison metrics
- partial-year aware annual CAGR utilities
- IPS compliance helper

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
