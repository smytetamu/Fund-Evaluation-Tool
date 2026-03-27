# Fund-Evaluation-Tool

A Streamlit-based MVP for evaluating and comparing investment funds.

## Overview

This tool allows users to:
- ingest fund data from CSV/Excel files
- calculate metrics (returns, volatility, Sharpe ratio, drawdown, etc.)
- run scenarios (stress tests, benchmark comparisons)
- export results to Excel reports
- persist data via a local SQLite database

## Stack

- Python 3.11+
- Streamlit (UI)
- Pandas / NumPy (data processing)
- SQLite via SQLAlchemy (persistence)
- openpyxl (Excel export)

## Quickstart

```bash
uv venv
uv pip install -e '.[dev]'
uv run streamlit run app/main.py
```

## Project Structure

```text
src/fund_evaluation_tool/
  ingestion/    # data loading & parsing
  metrics/      # performance metric calculations
  scenarios/    # scenario & stress-test logic
  export/       # Excel/report generation
  db/           # database models & session management
app/
  main.py       # Streamlit entrypoint
tests/          # pytest test suite
docs/           # documentation & references
```

## Status

MVP — work in progress.
