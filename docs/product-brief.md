# Product Brief — Fund Evaluation Tool

## Overview

The Fund Evaluation Tool is a web-based application that replaces a complex Excel/VBA workbook with a maintainable, collaborative Python stack. It helps investment professionals compare funds, apply fee calculations, and generate IPS-compliant analysis.

## Problem Being Solved

The legacy system (Excel + ~2000 lines of VBA) is powerful but fragile:
- Macro-enabled workbooks are hard to audit and version-control
- Multi-user collaboration requires manual file exchange
- Extending functionality means more VBA complexity
- No clear separation between data, logic, and presentation

## Target Users

- Investment analysts evaluating funds for IPS compliance
- Portfolio managers comparing fund performance across time horizons
- Compliance reviewers checking fee calculations against fund literature

## Product Goals

| Priority | Goal |
|----------|------|
| P0 | Replicate core fund comparison workflow in a web UI |
| P0 | Support literature-based fee calculation (hard/soft hurdle, HWM) |
| P1 | Export reports to Excel for presentation/distribution |
| P1 | Score funds against IPS targets |
| P2 | What-if and scenario analysis (inflation stress, Monte Carlo) |
| P2 | Multi-user project/session management |

## Success Criteria (MVP)

- An analyst can load fund return data, configure fee terms, run the core metrics, and export a comparison report to Excel
- All fee calculation modes from the legacy tool are supported
- Performance is acceptable for up to 20 funds × 20 years

## Non-Goals (MVP)

- Live data feeds (Bloomberg, Refinitiv)
- PDF/PowerPoint generation
- User accounts or authentication
- Factor decomposition or attribution analysis

## Relationship to Legacy System

The legacy Excel workbook (`IPS_MultiFund_Model_v13.2.xlsm`) is the reference implementation. All calculation logic should be validated against it. See `docs/workbook-inventory-plan.md` for the structured inspection plan.
