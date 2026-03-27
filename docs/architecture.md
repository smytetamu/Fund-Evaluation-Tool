# Architecture — Fund Evaluation Tool MVP

## Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| UI | Streamlit | Rapid prototyping, no JS required, good for data-heavy forms |
| Business logic | Python 3.11+ | Clean separation from UI, testable in isolation |
| Data storage | SQLite (via SQLAlchemy) | Zero-infrastructure, portable, sufficient for MVP scale |
| Calculations | pandas + numpy | Industry-standard for financial time series |
| Export | openpyxl | Excel generation without requiring Excel |

## Directory Layout

```
fund-evaluation-tool/
├── app/                    # Streamlit pages and UI components
│   ├── main.py             # Entry point, sidebar nav
│   ├── pages/
│   │   ├── funds.py        # Fund CRUD and fee config
│   │   ├── returns.py      # Return data entry
│   │   ├── comparison.py   # Results and comparison table
│   │   └── export.py       # Excel export trigger
│   └── components/         # Reusable UI widgets
├── src/                    # Core business logic (no Streamlit imports)
│   ├── models/             # SQLAlchemy ORM models
│   │   ├── fund.py
│   │   ├── return_data.py
│   │   └── fee_terms.py
│   ├── engine/             # Calculation engine
│   │   ├── fee_engine.py   # Fee waterfall logic
│   │   ├── metrics.py      # Performance metric calculations
│   │   └── comparison.py   # Fund comparison orchestration
│   ├── export/
│   │   └── excel.py        # openpyxl report generation
│   └── db.py               # DB session factory
├── tests/                  # Pytest unit and integration tests
│   ├── test_fee_engine.py
│   ├── test_metrics.py
│   └── fixtures/           # Sample fund data for tests
├── docs/                   # Project documentation
├── data/                   # SQLite DB file (gitignored in production)
└── requirements.txt
```

## Data Model (SQLite)

### `funds`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT | Unique fund identifier |
| include | BOOLEAN | Include in current analysis |
| fee_mode | TEXT | `net_provided` / `apply_literature` / `gross_not_applied` |
| created_at | DATETIME | |

### `fee_terms`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| fund_id | INTEGER FK | |
| mgmt_fee_pct | REAL | Annual management fee % |
| mgmt_accrual | TEXT | `monthly` / `quarterly` / `annual` |
| perf_fee_pct | REAL | Performance fee % |
| hurdle_type | TEXT | `fixed` / `cpi_plus` / `benchmark` / `absolute` |
| hurdle_rate | REAL | Rate for fixed/cpi_plus types |
| hwm_enabled | BOOLEAN | |
| hwm_reset | TEXT | `none` / `annual` / `periodic` |
| perf_fee_logic | TEXT | `hard` / `soft` / `catchup` |
| catchup_pct | REAL | Catch-up % if applicable |
| notes | TEXT | Literature reference |

### `return_data`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| fund_id | INTEGER FK | |
| year | INTEGER | Calendar year |
| fund_return | REAL | Decimal (e.g. 0.12 = 12%) |
| spx_return | REAL | Benchmark return for same period |
| is_partial | BOOLEAN | |
| months_in_period | INTEGER | 12 for full year |
| source_notes | TEXT | |

## Calculation Flow

```
Return data (raw)
     │
     ▼
Fee Engine (fee_engine.py)
  - Mode check
  - Management fee deduction
  - Hurdle/HWM tracking
  - Performance fee waterfall
     │
     ▼
Net Returns per fund/year
     │
     ▼
Metrics Engine (metrics.py)
  - CAGR, vol, drawdown, ratios
  - IPS compliance check
     │
     ▼
Comparison Orchestrator
  - Align to common start date
  - Assemble comparison table (DataFrame)
     │
     ├──► Streamlit table (comparison.py page)
     └──► Excel export (excel.py)
```

## Key Design Principles

1. **Engine is UI-agnostic.** All `src/engine/` code takes plain Python objects/DataFrames as input and returns DataFrames. No Streamlit imports in `src/`.
2. **Fee engine mirrors legacy waterfall exactly.** Step-by-step matching the VBA logic; see `docs/workbook-inventory-plan.md` for validation plan.
3. **Tests cover fee edge cases.** Hard hurdle, soft hurdle, catch-up, HWM reset — all must have test fixtures derived from the legacy workbook's example outputs.
4. **SQLite schema is append-friendly.** New columns added via Alembic migrations, not schema drops.

## Configuration

`src/config.py` (or environment variables):
- `DATABASE_URL` — SQLite path (default: `data/fund_eval.db`)
- `EXPORT_DIR` — Output directory for Excel files (default: `data/exports/`)

## Testing Strategy

- `tests/test_fee_engine.py` — Unit tests for every fee mode and hurdle combination
- `tests/test_metrics.py` — CAGR, Sharpe, drawdown calculations validated against known values
- `tests/test_comparison.py` — Integration: full fund → metrics pipeline
- Fixtures in `tests/fixtures/` include at least one fund per fee mode with expected outputs hand-verified against legacy workbook
