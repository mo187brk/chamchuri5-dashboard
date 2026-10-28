"""Single home for every assumption the dashboard uses.

Values marked MEASURED / SUPPLIED come from the project files; values marked
ASSUMED are placeholders until quotes or measurements exist. The Methodology
page prints this table so readers can see what is behind each number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"

BUILDING_NAME = "Chamchuri 5"
BUILDING_SITE = "Chulalongkorn University, Bangkok"
LOAD_YEAR = 2019
HOURS_PER_YEAR = 8760


@dataclass(frozen=True)
class Tariff:
    """MEA Type 3.2 TOU (SUPPLIED) with Ft and VAT. The building's real category is unconfirmed."""

    on_peak_base: float = 4.20        # THB/kWh before Ft and VAT
    off_peak_base: float = 2.65       # THB/kWh before Ft and VAT
    demand_charge: float = 132.93     # THB/kW/month on the highest on-peak hourly demand
    service_charge: float = 312.24    # THB/month
    ft: float = 0.1623                # THB/kWh
    vat: float = 0.07
    on_peak_start: int = 9            # Mon-Fri, hour of day (inclusive)
    on_peak_end: int = 22             # Mon-Fri, hour of day (exclusive)
    export_price: float = 2.20        # THB/kWh paid for exported energy (SUPPLIED); no VAT applied

    @property
    def on_peak_rate(self) -> float:
        """All-in energy price during on-peak hours, THB/kWh."""
        return (self.on_peak_base + self.ft) * (1 + self.vat)

    @property
    def off_peak_rate(self) -> float:
        """All-in energy price during off-peak hours, THB/kWh."""
        return (self.off_peak_base + self.ft) * (1 + self.vat)


@dataclass(frozen=True)
class Plant:
    """Rooftop PV plant."""

    existing_kwp: float = 20.0        # ESTIMATED from a satellite image (+-25%), no metered output
    new_kwp: float = 74.25            # 135 modules x 550 W on ~350 m2 of the empty half of the roof
    roof_area_m2: float = 500.0       # roof area assumed in the sizing study
    module_area_m2: float = 350.0     # usable module area in the sizing study
    measured_free_roof_m2: float = 592.38  # polygon measured on satellite imagery (free half)


@dataclass(frozen=True)
class Finance:
    """Economic assumptions. All ASSUMED except where the Excel model states otherwise."""

    pv_cost_per_kwp: float = 26_000.0   # THB/kWp installed, ASSUMED rooftop C&I price
    pv_om_per_kwp: float = 260.0        # THB/kWp/year, ASSUMED (about 1% of capex)
    discount_rate: float = 0.07
    escalation: float = 0.02            # tariff and O&M escalation per year
    degradation: float = 0.005          # PV degradation per year (applied to PV savings)
    horizon_years: int = 20


@dataclass(frozen=True)
class DsmDefaults:
    """Demand-side rules. The two cut percentages are scenario assumptions, not measurements."""

    light_cut: float = 0.40           # share of lighting load removed in off-hours
    ac_cut: float = 0.25              # share of air-conditioning load removed in off-hours
    work_start_hour: int = 6          # first working hour on a workday
    work_end_hour: int = 20           # first non-working hour on a workday (off-hours start here)
    low_use_fraction: float = 0.65    # a workday below this share of the median workday is "low-use"


@dataclass(frozen=True)
class Grid:
    """Grid connection of the building (from the Excel inputs; the power factor is ASSUMED)."""

    transformer_kva: float = 1250.0
    power_factor: float = 0.9

    @property
    def limit_kw(self) -> float:
        """Active power the transformer can carry, in either direction."""
        return self.transformer_kva * self.power_factor


TARIFF = Tariff()
GRID = Grid()
PLANT = Plant()
FINANCE = Finance()
DSM = DsmDefaults()

# Default exchange rate shown in the sidebar (editable). Quote of 2026-10-27: 1 USD = 33.78 THB.
DEFAULT_THB_PER_USD = 33.78
