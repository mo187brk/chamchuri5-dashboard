"""Number and currency formatting. THB is the working currency; USD is shown alongside."""

from __future__ import annotations

from dataclasses import dataclass

from .config import DEFAULT_THB_PER_USD

THB = "THB"
USD = "USD"
_SYMBOL = {THB: "฿", USD: "$"}


def _compact(value: float, decimals: int = 2) -> str:
    """12,345,678 -> 12.35M; 12,345 -> 12.3k; 123 -> 123."""
    magnitude = abs(value)
    if magnitude >= 1e6:
        return f"{value / 1e6:,.{decimals}f}M"
    if magnitude >= 1e4:
        return f"{value / 1e3:,.0f}k"
    if magnitude >= 1e3:
        return f"{value / 1e3:,.1f}k"
    return f"{value:,.0f}"


@dataclass(frozen=True)
class Currency:
    """Display currency plus the exchange rate used for the equivalent."""

    code: str = THB
    thb_per_usd: float = DEFAULT_THB_PER_USD

    def __post_init__(self) -> None:
        if self.code not in (THB, USD):
            raise ValueError(f"Unsupported currency {self.code!r}")
        if not self.thb_per_usd > 0:
            raise ValueError("Exchange rate must be positive")

    @property
    def other(self) -> str:
        return USD if self.code == THB else THB

    def to_display(self, thb: float) -> float:
        """Convert an amount held in THB to the display currency."""
        return thb if self.code == THB else thb / self.thb_per_usd

    def to_other(self, thb: float) -> float:
        """Convert an amount held in THB to the secondary currency."""
        return thb / self.thb_per_usd if self.code == THB else thb

    def money(self, thb: float, decimals: int = 2) -> str:
        """Compact amount in the display currency, e.g. ฿9.92M or $296k."""
        value = self.to_display(thb)
        sign = "-" if value < 0 else ""
        return f"{sign}{_SYMBOL[self.code]}{_compact(abs(value), decimals)}"

    def secondary(self, thb: float, decimals: int = 2) -> str:
        """Compact amount in the other currency, prefixed with its code, e.g. 'USD 296k'."""
        value = self.to_other(thb)
        sign = "-" if value < 0 else ""
        return f"{sign}{self.other} {_compact(abs(value), decimals)}"

    def both(self, thb: float, decimals: int = 2) -> str:
        """'฿9.92M (USD 296k)'"""
        return f"{self.money(thb, decimals)} ({self.secondary(thb, decimals)})"

    @property
    def unit(self) -> str:
        return self.code


def mwh(kwh: float, decimals: int = 1) -> str:
    return f"{kwh / 1e3:,.{decimals}f} MWh"


def kw(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f} kW"


def pct(fraction: float, decimals: int = 1) -> str:
    return f"{100 * fraction:,.{decimals}f}%"


def years(value: float | None) -> str:
    """Payback in years; 'Immediate' when there is no capital cost, 'n/a' when it never pays back."""
    if value is None or value != value:   # None, or NaN as pandas stores a missing payback
        return "No payback"
    if value == 0:
        return "Immediate"
    return f"{value:,.1f} years"
