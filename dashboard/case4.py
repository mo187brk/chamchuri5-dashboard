"""Case 4 (what-if): an off-site plant whose output is credited against the building's bill.

The roof has no room for more panels. The scenario asks: what if other land were found, a 550 kWp
plant built there, its whole output fed into the grid and credited on the Chamchuri 5 bill
(virtual net metering)? The roof arrays of Cases 2-3 stay as they are and keep serving the building.

Modelling choices
    * All of the plant's energy is exported and credited at `settings.c4_credit` THB/kWh (a flat price),
      or, in the "retail TOU" sensitivity, at the building's own energy price for that hour.
    * The plant does not lower the building's grid import, so the billed demand does not change.
    * Energy that the roof arrays cannot use (almost none) is credited at the same price.
    * No wheeling, administration or grid-connection cost is included: they are unknown.

Inputs shipped in ./data
    case4_plant.json          system data of the plant (550 kWp, 1,000 x 550 W, tilt, azimuth, losses)
    case4_plant_profile.csv   output in Wh per kWp for the average day of each month (24 hours x 12 months)

Optional hourly override
    case4_expanded.csv        datetime, pv_expanded_kw  (8,760 rows, same timestamps as the 2019 load).
    When this file exists it replaces the monthly profile, e.g. once a real hourly series is available.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .config import DATA_DIR, FINANCE, GRID, PLANT, TARIFF, Finance, Plant, Tariff
from .data import HourlyData
from .engine import MONTH_LABELS, Calendar, Economics, Scenario, compute_bill, project_economics, retail_rate

if TYPE_CHECKING:  # imported for type hints only; keeps this module independent of model.py at run time
    from .model import CaseResults, Settings

PLANT_FILE = DATA_DIR / "case4_plant.json"
PROFILE_FILE = DATA_DIR / "case4_plant_profile.csv"
EXPANDED_FILE = DATA_DIR / "case4_expanded.csv"
REQUIRED_COLUMNS = ("datetime", "pv_expanded_kw")

# Names reserved for the results, so other modules can refer to them (filled in by run_case4).
PV_EXPANDED_KW: np.ndarray | None = None
EXPORT_REVENUE_THB: float | None = None


# --------------------------------------------------------------------------- plant data
@dataclass(frozen=True)
class PlantSpec:
    """System data of the Case 4 plant, as supplied by the project team."""

    capacity_kwp: float
    modules: int
    module_kw: float
    module_area_m2: float
    tilt_deg: float
    azimuth_deg: float
    losses_pct: float
    latitude_deg_n: float
    longitude_deg_e: float
    technology: str
    source: str

    def __post_init__(self) -> None:
        if self.capacity_kwp <= 0 or self.modules <= 0 or self.module_kw <= 0:
            raise ValueError("Plant capacity, module count and module power must be positive")
        if abs(self.modules * self.module_kw - self.capacity_kwp) > 0.001 * self.capacity_kwp:
            raise ValueError("Plant capacity does not equal modules x module power")

    @property
    def module_area_total_m2(self) -> float:
        """Land or roof area taken by the modules alone."""
        return self.modules * self.module_area_m2


def load_plant_spec(path: Path = PLANT_FILE) -> PlantSpec:
    """Read the plant's system data."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        return PlantSpec(
            capacity_kwp=float(raw["capacity_kwp"]), modules=int(raw["modules"]), module_kw=float(raw["module_kw"]),
            module_area_m2=float(raw["module_area_m2"]), tilt_deg=float(raw["tilt_deg"]),
            azimuth_deg=float(raw["azimuth_deg"]), losses_pct=float(raw["system_losses_pct"]),
            latitude_deg_n=float(raw["latitude_deg_n"]), longitude_deg_e=float(raw["longitude_deg_e"]),
            technology=str(raw["technology"]), source=str(raw["source"]),
        )
    except KeyError as exc:
        raise ValueError(f"{path.name} is missing the field {exc}") from exc


def load_profile(path: Path = PROFILE_FILE) -> np.ndarray:
    """Output in Wh per kWp, array [24 hours x 12 months] (average day of each month)."""
    frame = pd.read_csv(path)
    if list(frame.columns) != ["hour", *MONTH_LABELS]:
        raise ValueError(f"{path.name} must have the columns hour, Jan ... Dec")
    if frame["hour"].tolist() != list(range(24)):
        raise ValueError(f"{path.name} must have one row for each hour 0..23")
    values = frame[MONTH_LABELS].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1200).any():
        raise ValueError(f"{path.name} must hold finite Wh per kWp values between 0 and 1,200")
    return values


def hourly_from_profile(profile_wh_per_kwp: np.ndarray, cal: Calendar, capacity_kwp: float) -> np.ndarray:
    """Hourly kW of the plant: the month's average-day profile applied to every day of that month."""
    return profile_wh_per_kwp[cal.hour, cal.month - 1] / 1000.0 * capacity_kwp


def validate_expanded(frame: pd.DataFrame, data: HourlyData) -> None:
    """Raise ValueError unless the file is a clean hourly series aligned with the load year."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"{EXPANDED_FILE.name} is missing columns: {missing}")
    if len(frame) != data.calendar.n_hours:
        raise ValueError(f"Expected {data.calendar.n_hours} rows, found {len(frame)}")
    stamps = pd.DatetimeIndex(frame["datetime"])
    if not stamps.equals(data.calendar.index):
        raise ValueError("Timestamps do not match the 2019 hourly load file")
    values = pd.to_numeric(frame["pv_expanded_kw"], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy()).all():
        raise ValueError("pv_expanded_kw contains missing or non-numeric values")
    if (values < 0).any():
        raise ValueError("pv_expanded_kw must not be negative")


def load_expanded_plant(data: HourlyData, path: Path = EXPANDED_FILE) -> np.ndarray | None:
    """Hourly kW from the optional override file, or None when it does not exist."""
    if not path.exists():
        return None
    frame = pd.read_csv(path, parse_dates=["datetime"])
    validate_expanded(frame, data)
    return frame["pv_expanded_kw"].to_numpy(dtype=float)


def plant_available() -> bool:
    """True when the plant data is in ./data (monthly profile or hourly override)."""
    return PLANT_FILE.exists() and (PROFILE_FILE.exists() or EXPANDED_FILE.exists())


def plant_hourly_kw(data: HourlyData, spec: PlantSpec) -> tuple[np.ndarray, str]:
    """Hourly kW of the plant and a short label of where it came from."""
    override = load_expanded_plant(data)
    if override is not None:
        return override, "hourly file (case4_expanded.csv)"
    return hourly_from_profile(load_profile(), data.calendar, spec.capacity_kwp), "typical day for each month (PVGIS-based)"


# --------------------------------------------------------------------------- simulation
def simulate_offsite(
    data: HourlyData,
    load_kw: np.ndarray,
    roof_pv_kw: np.ndarray,
    plant_kw: np.ndarray,
    credit_thb_per_kwh: float,
    export_rate: np.ndarray | None = None,
) -> Scenario:
    """The building with its roof arrays, plus an off-site plant whose whole output is credited.

    The roof arrays serve the load first. Everything the plant makes (and any roof surplus) is
    exported and credited at a flat price or, if given, at `export_rate` for every hour.
    """
    if credit_thb_per_kwh < 0:
        raise ValueError("The credit must not be negative")
    load, roof, plant = (np.asarray(a, float) for a in (load_kw, roof_pv_kw, plant_kw))
    if not (load.shape == roof.shape == plant.shape == (data.calendar.n_hours,)):
        raise ValueError("load, roof PV and plant output must have one value per calendar hour")
    if (plant < 0).any():
        raise ValueError("The plant output must not be negative")
    tariff = Tariff(**{**TARIFF.__dict__, "export_price": float(credit_thb_per_kwh)})
    used = np.minimum(roof, load)
    grid = load - used
    export = (roof - used) + plant
    bill = compute_bill(grid, export, data.calendar, tariff, export_rate)
    return Scenario(load, roof + plant, used, grid, export, bill, data.calendar.on_peak)


@dataclass(frozen=True)
class Case4Results:
    """One simulated year of the what-if and the economics of building the plant."""

    spec: PlantSpec
    source: str
    credit: float                  # THB/kWh
    plant_kw: np.ndarray           # output of the off-site plant (all exported)
    roof_pv_kw: np.ndarray         # existing + new roof arrays (Cases 2-3)
    scenario: Scenario             # pv_kw = roof + plant; export_kw includes the whole plant
    bill_case1_thb: float
    bill_case3_thb: float
    vs_case3: Economics            # building the plant, against Case 3
    vs_case1: Economics            # the whole programme (new roof PV + rules + plant), against Case 1

    @property
    def plant_kwh(self) -> float:
        return float(self.plant_kw.sum())

    @property
    def offset_share(self) -> float:
        """Plant energy credited, as a share of the building's annual consumption."""
        return self.plant_kwh / self.scenario.load_kwh

    @property
    def saving_vs_case3_thb(self) -> float:
        return self.bill_case3_thb - self.scenario.bill.total_thb

    @property
    def saving_vs_case1_thb(self) -> float:
        return self.bill_case1_thb - self.scenario.bill.total_thb

    @property
    def export_revenue_thb(self) -> float:
        """Credit earned by everything sent to the grid (the plant plus any roof surplus)."""
        return float(-self.scenario.bill.export_credit_thb) + 0.0   # "+ 0.0" turns -0.0 into 0.0

    @property
    def peak_export_kw(self) -> float:
        return float(self.scenario.export_kw.max())

    @property
    def exceeds_transformer(self) -> bool:
        """True when the power sent to the grid would exceed what the transformer can carry (assumed rating)."""
        return self.peak_export_kw > GRID.limit_kw

    @property
    def module_area_needed_m2(self) -> float:
        return self.spec.module_area_total_m2


def run_case4(
    data: HourlyData,
    results: "CaseResults",
    settings: "Settings",
    spec: PlantSpec | None = None,
    plant: Plant = PLANT,
    fin: Finance = FINANCE,
) -> Case4Results:
    """Simulate the what-if for the credit in `settings`."""
    spec = spec or load_plant_spec()
    plant_kw, source = plant_hourly_kw(data, spec)
    roof_pv = results.pv_existing_kw + results.pv_new_kw
    scenario = simulate_offsite(data, results.case3.load_kw, roof_pv, plant_kw, settings.c4_credit)

    price, om = settings.pv_cost_per_kwp, fin.pv_om_per_kwp
    bill1, bill3, bill4 = results.case1.bill.total_thb, results.case3.bill.total_thb, scenario.bill.total_thb
    vs_case3 = project_economics(spec.capacity_kwp * price, bill3 - bill4, 0.0, spec.capacity_kwp * om, fin)

    built = plant.new_kwp + spec.capacity_kwp                  # everything installed after today
    rules_part = results.dsm_saving_thb
    vs_case1 = project_economics(
        built * price + settings.dsm_cost_thb, (bill1 - bill4) - rules_part, rules_part, built * om, fin
    )
    return Case4Results(
        spec=spec, source=source, credit=float(settings.c4_credit), plant_kw=plant_kw, roof_pv_kw=roof_pv,
        scenario=scenario, bill_case1_thb=bill1, bill_case3_thb=bill3, vs_case3=vs_case3, vs_case1=vs_case1,
    )


# --------------------------------------------------------------------------- value of the credit
def credit_options(
    data: HourlyData, results: "CaseResults", c4: Case4Results, settings: "Settings", fin: Finance = FINANCE
) -> pd.DataFrame:
    """The same plant under three ways of crediting its energy (one row each)."""
    options = [
        ("No credit", 0.0, None),
        (f"Thai buy-back ({TARIFF.export_price:g} THB/kWh)", TARIFF.export_price, None),
        ("Retail TOU price (upper bound)", 0.0, retail_rate(data.calendar)),
    ]
    capex = c4.spec.capacity_kwp * settings.pv_cost_per_kwp
    om = c4.spec.capacity_kwp * fin.pv_om_per_kwp
    rows = []
    for label, flat, hourly in options:
        s = simulate_offsite(data, results.case3.load_kw, c4.roof_pv_kw, c4.plant_kw, flat, hourly)
        saving = c4.bill_case3_thb - s.bill.total_thb
        eco = project_economics(capex, saving, 0.0, om, fin)
        revenue = float(-s.bill.export_credit_thb) + 0.0
        rows.append((label, revenue, s.bill.total_thb, saving, eco.payback_years, eco.npv_thb))
    return pd.DataFrame(
        rows, columns=["Credit", "Credit earned", "Annual bill", "Saving vs Case 3", "Payback (years)", "NPV"]
    ).set_index("Credit")


def credit_curve(
    c4: Case4Results, settings: "Settings", fin: Finance = FINANCE, max_credit: float | None = None, points: int = 25
) -> pd.DataFrame:
    """Saving and payback of building the plant for flat credits from 0 to the on-peak retail price.

    The exported energy does not depend on the credit, so the saving is exactly linear in it:
    saving(c) = saving(chosen) + (c - chosen) * exported kWh.
    """
    top = TARIFF.on_peak_rate if max_credit is None else max_credit
    credits = np.linspace(0.0, top, points)
    saving = c4.saving_vs_case3_thb + (credits - c4.credit) * c4.scenario.export_kwh
    capex = c4.spec.capacity_kwp * settings.pv_cost_per_kwp
    net = saving - c4.spec.capacity_kwp * fin.pv_om_per_kwp
    payback = np.where(net > 0, capex / np.where(net > 0, net, 1.0), np.nan)
    return pd.DataFrame({"credit": credits, "saving_thb": saving, "payback_years": payback})
