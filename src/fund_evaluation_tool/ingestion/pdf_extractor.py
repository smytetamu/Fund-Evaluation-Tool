"""AI-powered PDF extraction for fund documents using Claude API.

Accepts a raw PDF (bytes) and returns structured fund-performance rows
matching the legacy CSV schema:

    Fund, Year, Fund_Return, SPX_Return, Is_Partial_Year, Months_In_Period,
    Fee_Mode, Mgmt_Fee_%, Perf_Fee_%, Hurdle_Type, Hurdle_Value,
    HWM_Enabled, Source_Notes

Claude reads the PDF directly (base64-encoded) via the Messages API.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional

import anthropic

_LEGACY_COLUMNS = [
    "Fund",
    "Year",
    "Fund_Return",
    "SPX_Return",
    "Is_Partial_Year",
    "Months_In_Period",
    "Fee_Mode",
    "Mgmt_Fee_%",
    "Perf_Fee_%",
    "Hurdle_Type",
    "Hurdle_Value",
    "HWM_Enabled",
    "Source_Notes",
]

_EXTRACTION_PROMPT = """You are a fund document parser. Extract all fund performance data from this document and return it as a JSON array.

Each element represents ONE fund for ONE calendar year with these exact fields:
- "Fund": string — the fund name
- "Year": integer — the year (YYYY)
- "Fund_Return": float — annual return as decimal (e.g. 0.152 for 15.2%); null if not found
- "SPX_Return": float — S&P 500 or stated benchmark annual return as decimal; null if not found
- "Is_Partial_Year": 0 or 1 — 1 if the period covers fewer than 12 months
- "Months_In_Period": integer — months in period (12 for a full calendar year)
- "Fee_Mode": string — e.g. "Standard", "Performance", or null
- "Mgmt_Fee_%": float — annual management fee as decimal (e.g. 0.02 for 2%); null if not found
- "Perf_Fee_%": float — performance/incentive fee as decimal (e.g. 0.20 for 20%); null if not found
- "Hurdle_Type": string — e.g. "Absolute", "Relative", "None", or null
- "Hurdle_Value": float — hurdle rate as decimal; null if not found
- "HWM_Enabled": 0 or 1 — 1 if high-water mark is mentioned, otherwise 0
- "Source_Notes": string — e.g. "Audited", "Unaudited", "Estimated", or null

Rules:
- Convert percentage returns to decimals (15.2% → 0.152).
- Include ALL years of performance data found in the document.
- If multiple funds appear, emit one row per fund per year.
- Use null for fields that are genuinely absent — do not guess.
- Return ONLY a valid JSON array, no markdown fences, no other text.

Example:
[
  {"Fund": "Kell Capital", "Year": 2024, "Fund_Return": 0.152, "SPX_Return": 0.231,
   "Is_Partial_Year": 0, "Months_In_Period": 12, "Fee_Mode": "Standard",
   "Mgmt_Fee_%": 0.015, "Perf_Fee_%": 0.20, "Hurdle_Type": "Absolute",
   "Hurdle_Value": 0.06, "HWM_Enabled": 1, "Source_Notes": "Unaudited"}
]"""


def extract_fund_data_from_pdf(
    pdf_bytes: bytes,
    api_key: Optional[str] = None,
    model: str = "claude-opus-4-6",
) -> list[dict]:
    """Extract fund performance data from a PDF using Claude.

    Parameters
    ----------
    pdf_bytes:
        Raw bytes of the PDF file.
    api_key:
        Anthropic API key. Falls back to ``ANTHROPIC_API_KEY`` env var.
    model:
        Claude model to use. Defaults to claude-opus-4-6.

    Returns
    -------
    list[dict]
        One dict per fund-year row, keys matching ``_LEGACY_COLUMNS``.

    Raises
    ------
    ValueError
        If no API key is available, or if Claude returns unparseable output.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "No Anthropic API key provided. Set the ANTHROPIC_API_KEY environment "
            "variable or pass api_key= to this function."
        )

    client = anthropic.Anthropic(api_key=key)
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": _EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if the model wraps the JSON anyway
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Claude returned non-JSON output:\n{raw[:400]}"
        ) from exc

    if not isinstance(rows, list):
        raise ValueError(
            f"Expected a JSON array from Claude, got {type(rows).__name__}."
        )

    return rows


def rows_to_legacy_csv_bytes(rows: list[dict]) -> bytes:
    """Serialise extracted rows to CSV bytes matching the legacy schema."""
    import io
    import pandas as pd

    df = pd.DataFrame(rows, columns=_LEGACY_COLUMNS)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
