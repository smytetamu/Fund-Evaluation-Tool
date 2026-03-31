"""Fund configuration model — workbook ``Fund_Details`` parity.

Stores per-fund metadata (inclusion flags, strategy/return type, fee terms,
hurdle/HWM, liquidity notes) and anchored comparison window settings.
Persists in Streamlit session state; an optional SQLite path is accepted for
durable storage via the ``db`` module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Fund-level configuration
# ---------------------------------------------------------------------------

StrategyType = Literal[
    "Equity Long/Short",
    "Equity Long Only",
    "Fixed Income",
    "Multi-Strategy",
    "Global Macro",
    "Event Driven",
    "Real Assets",
    "Private Equity",
    "Other",
]

ReturnType = Literal["Gross", "Net"]
FeeMode = Literal["Management Only", "Management + Performance", "None"]
FeeStatus = Literal["Active", "Waived", "N/A"]


@dataclass
class FundDetails:
    """Configuration metadata for a single fund (mirrors workbook Fund_Details sheet).

    All fields default to sensible placeholders so callers can construct a
    minimal instance and fill in only what they know.
    """

    name: str
    include: bool = True
    strategy_type: StrategyType = "Other"
    return_type: ReturnType = "Gross"
    fee_mode: FeeMode = "Management + Performance"
    fee_status: FeeStatus = "Active"
    management_fee_pct: float | None = None  # e.g. 0.02 for 2%
    performance_fee_pct: float | None = None  # e.g. 0.20 for 20%
    hurdle_rate_pct: float | None = None  # e.g. 0.08 for 8% hurdle
    high_water_mark: bool = False
    liquidity_notes: str = ""
    source_note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Session-level fund config store
# ---------------------------------------------------------------------------


@dataclass
class FundDetailsConfig:
    """Collection of FundDetails keyed by fund name.

    Designed to live in ``st.session_state`` between Streamlit reruns.
    """

    _funds: dict[str, FundDetails] = field(default_factory=dict)

    def get(self, name: str) -> FundDetails:
        if name not in self._funds:
            self._funds[name] = FundDetails(name=name)
        return self._funds[name]

    def set(self, details: FundDetails) -> None:
        self._funds[details.name] = details

    def all_funds(self) -> list[FundDetails]:
        return list(self._funds.values())

    def included_funds(self) -> list[str]:
        return [d.name for d in self._funds.values() if d.include]

    def sync_from_names(self, names: list[str]) -> None:
        """Ensure an entry exists for every fund in ``names``; remove stale ones."""
        for name in names:
            self.get(name)
        for stale in set(self._funds) - set(names):
            del self._funds[stale]


# ---------------------------------------------------------------------------
# Anchored comparison window
# ---------------------------------------------------------------------------


@dataclass
class AnchorWindow:
    """Workbook-parity anchor/comparison window settings.

    The effective start year drives all fund and benchmark metric windows so
    that comparisons are anchored to the same time horizon.

    anchor_fund:
        Name of the fund used to derive the natural anchor start year (i.e.
        the first year that fund has data).
    anchor_start_year:
        Derived from anchor_fund's earliest data year.  ``None`` until
        resolved from an uploaded series.
    override_start_year:
        Optional manual override.  When set, ``effective_start_year`` uses
        this value instead of ``anchor_start_year``.
    effective_start_year:
        The year applied to clip all series before metric computation.
        Equals ``override_start_year`` if set, otherwise ``anchor_start_year``.
    """

    anchor_fund: str | None = None
    anchor_start_year: int | None = None
    override_start_year: int | None = None

    @property
    def effective_start_year(self) -> int | None:
        if self.override_start_year is not None:
            return self.override_start_year
        return self.anchor_start_year

    def resolve_anchor(self, returns_wide: "pd.DataFrame") -> None:  # noqa: F821
        """Set ``anchor_start_year`` from the anchor fund's first data year."""
        import pandas as pd

        if self.anchor_fund is None or self.anchor_fund not in returns_wide.columns:
            self.anchor_start_year = None
            return
        series = returns_wide[self.anchor_fund].dropna()
        if series.empty:
            self.anchor_start_year = None
            return
        self.anchor_start_year = int(series.index.min().year)

    def clip_to_window(self, returns_wide: "pd.DataFrame") -> "pd.DataFrame":  # noqa: F821
        """Return a copy of ``returns_wide`` clipped to ``effective_start_year``."""
        import pandas as pd

        esy = self.effective_start_year
        if esy is None:
            return returns_wide
        cutoff = pd.Timestamp(f"{esy}-01-01")
        return returns_wide.loc[returns_wide.index >= cutoff]
