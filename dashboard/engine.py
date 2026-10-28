"""Calculation engine: calendar, PV, tariff bill, demand-side rules and project economics.

Everything here is a pure function of NumPy arrays and small frozen dataclasses, so it
can be unit-tested without Streamlit. The tariff and cash-flow logic reproduces the
Excel strategy model exactly (see tests/test_engine.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DSM, FINANCE, TARIFF, DsmDefaults, Finance, Tariff

NEW_ARRAY_AS_SUPPLIED = "as_supplied"
NEW_ARRAY_SOUTH = "south"

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# --------------------------------------------------------------------------- calendar
@dataclass(frozen=True)
class Calendar:
    """Per-hour calendar facts, computed once from the timestamps."""

    index: pd.DatetimeIndex
    month: np.ndarray          # 1..12
    hour: np.ndarray           # 0..23
    day_id: np.ndarray         # 0..n_days-1, one id per calendar day
    weekend: np.ndarray        # True on Saturday and Sunday
    on_peak: np.ndarray        # True Mon-Fri inside the on-peak window
    month_starts: np.ndarray   # row index where each month begins (data must be time-sorted)
    n_days: int

    @property
    def n_hours(self) -> int:
        return len(self.index)


def build_calendar(index: pd.DatetimeIndex, tariff: Tariff = TARIFF) -> Calendar:
    """Derive calendar arrays from a sorted, hourly DatetimeIndex."""
    if not index.is_monotonic_increasing or index.has_duplicates:
        raise ValueError("Timestamps must be sorted and unique")
    month = index.month.to_numpy()
    hour = index.hour.to_numpy()
    weekend = index.dayofweek.to_numpy() >= 5
    on_peak = (~weekend) & (hour >= tariff.on_peak_start) & (hour < tariff.on_peak_end)

    _, day_id = np.unique(index.normalize().to_numpy(), return_inverse=True)
    day_id = np.asarray(day_id).reshape(-1)

    starts = np.flatnonzero(np.r_[True, month[1:] != month[:-1]])
    if len(starts) != 12:
        raise ValueError(f"Expected one contiguous block per month (12), found {len(starts)}")
    return Calendar(index, month, hour, day_id, weekend, on_peak, starts, int(day_id.max()) + 1)


# --------------------------------------------------------------------------- PV
def pv_output(
    shape_existing: np.ndarray,
    shape_new: np.ndarray,
    existing_kwp: float,
    new_kwp: float,
    new_array: str = NEW_ARRAY_AS_SUPPLIED,
) -> tuple[np.ndarray, np.ndarray]:
    """Hourly kW of the existing and the new array.

    `new_array="south"` gives the new array the existing (south-facing) profile; the
    default uses the profile supplied for it, which may be north-facing (open point in
    the Excel model).
    """
    if new_array not in (NEW_ARRAY_AS_SUPPLIED, NEW_ARRAY_SOUTH):
        raise ValueError(f"Unknown new-array profile: {new_array!r}")
    shape_for_new = shape_existing if new_array == NEW_ARRAY_SOUTH else shape_new
    return existing_kwp * np.asarray(shape_existing, float), new_kwp * np.asarray(shape_for_new, float)


# --------------------------------------------------------------------------- bill
@dataclass(frozen=True)
class Bill:
    """Twelve monthly bill lines in THB (export credit is negative)."""

    monthly: pd.DataFrame

    @property
    def total_thb(self) -> float:
        return float(self.monthly["total_thb"].sum())

    @property
    def energy_thb(self) -> float:
        return float(self.monthly[["energy_on_thb", "energy_off_thb"]].sum().sum())

    @property
    def demand_thb(self) -> float:
        return float(self.monthly["demand_thb"].sum())

    @property
    def service_thb(self) -> float:
        return float(self.monthly["service_thb"].sum())

    @property
    def export_credit_thb(self) -> float:
        return float(self.monthly["export_credit_thb"].sum())


def compute_bill(
    grid_kw: np.ndarray,
    export_kw: np.ndarray,
    cal: Calendar,
    tariff: Tariff = TARIFF,
    export_rate: np.ndarray | None = None,
) -> Bill:
    """Bill for one year of hourly grid import and export under the TOU tariff.

    Demand is the highest *hourly* on-peak import of each month (the real bill uses
    15-minute averages, so demand charges are slightly understated).

    Exported energy is credited at `tariff.export_price` (a flat THB/kWh) unless
    `export_rate` gives a credit for every hour (e.g. net metering at the retail TOU price).
    """
    grid = np.asarray(grid_kw, float)
    export = np.asarray(export_kw, float)
    if grid.shape != (cal.n_hours,) or export.shape != grid.shape:
        raise ValueError("grid_kw and export_kw must have one value per calendar hour")
    if (grid < -1e-9).any() or (export < -1e-9).any():
        raise ValueError("grid_kw and export_kw must not be negative")
    if export_rate is None:
        credit_per_hour = export * tariff.export_price
    else:
        rate = np.asarray(export_rate, float)
        if rate.shape != grid.shape or (rate < 0).any():
            raise ValueError("export_rate must be a non-negative value for every calendar hour")
        credit_per_hour = export * rate

    starts = cal.month_starts
    cost = grid * np.where(cal.on_peak, tariff.on_peak_rate, tariff.off_peak_rate)
    on_peak_kw = np.where(cal.on_peak, grid, 0.0)
    vat = 1 + tariff.vat
    monthly = pd.DataFrame(
        {
            "energy_on_thb": np.add.reduceat(np.where(cal.on_peak, cost, 0.0), starts),
            "energy_off_thb": np.add.reduceat(np.where(cal.on_peak, 0.0, cost), starts),
            "demand_thb": np.maximum.reduceat(on_peak_kw, starts) * tariff.demand_charge * vat,
            "service_thb": np.full(12, tariff.service_charge * vat),
            "export_credit_thb": -np.add.reduceat(credit_per_hour, starts),
            "grid_kwh": np.add.reduceat(grid, starts),
            "peak_onpeak_kw": np.maximum.reduceat(on_peak_kw, starts),
        },
        index=pd.Index(MONTH_LABELS, name="month"),
    )
    monthly["total_thb"] = monthly[
        ["energy_on_thb", "energy_off_thb", "demand_thb", "service_thb", "export_credit_thb"]
    ].sum(axis=1)
    return Bill(monthly)


# --------------------------------------------------------------------------- scenario
@dataclass(frozen=True)
class Scenario:
    """One simulated year: load, PV and the resulting grid exchange and bill."""

    load_kw: np.ndarray
    pv_kw: np.ndarray
    used_kw: np.ndarray        # PV energy consumed in the building
    grid_kw: np.ndarray        # energy bought from the grid
    export_kw: np.ndarray      # PV surplus sent to the grid
    bill: Bill
    on_peak: np.ndarray

    @property
    def load_kwh(self) -> float:
        return float(self.load_kw.sum())

    @property
    def pv_kwh(self) -> float:
        return float(self.pv_kw.sum())

    @property
    def used_kwh(self) -> float:
        return float(self.used_kw.sum())

    @property
    def export_kwh(self) -> float:
        return float(self.export_kw.sum())

    @property
    def grid_kwh(self) -> float:
        return float(self.grid_kw.sum())

    @property
    def self_consumption(self) -> float:
        """Share of PV energy used inside the building (1.0 when nothing is exported)."""
        return self.used_kwh / self.pv_kwh if self.pv_kwh > 0 else 1.0

    @property
    def pv_share_of_load(self) -> float:
        return self.used_kwh / self.load_kwh

    @property
    def peak_grid_kw(self) -> float:
        """Highest hourly grid import at any time."""
        return float(self.grid_kw.max())

    @property
    def peak_onpeak_kw(self) -> float:
        """Highest hourly grid import in on-peak hours: the demand the tariff bills."""
        return float(self.grid_kw[self.on_peak].max())


def retail_rate(cal: Calendar, tariff: Tariff = TARIFF) -> np.ndarray:
    """All-in energy price for every hour (THB/kWh): the credit under net metering at the retail TOU price."""
    return np.where(cal.on_peak, tariff.on_peak_rate, tariff.off_peak_rate)


def simulate(
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    cal: Calendar,
    tariff: Tariff = TARIFF,
    export_rate: np.ndarray | None = None,
) -> Scenario:
    """Hour-by-hour balance: PV serves the load first, any surplus is exported."""
    load = np.asarray(load_kw, float)
    pv = np.asarray(pv_kw, float)
    used = np.minimum(pv, load)
    grid = load - used
    export = pv - used
    bill = compute_bill(grid, export, cal, tariff, export_rate)
    return Scenario(load, pv, used, grid, export, bill, cal.on_peak)


# --------------------------------------------------------------------------- demand-side rules
@dataclass(frozen=True)
class DsmRules:
    """Two off-hours rules: dim lighting and set back air-conditioning.

    Off-hours are every hour of weekends, plus workdays before `work_start_hour` and from
    `work_end_hour` on. Optionally the low-use workdays (probable holidays) count as
    off-hours all day.
    """

    light_cut: float = DSM.light_cut
    ac_cut: float = DSM.ac_cut
    work_start_hour: int = DSM.work_start_hour
    work_end_hour: int = DSM.work_end_hour
    low_use_as_holiday: bool = False

    def __post_init__(self) -> None:
        for name in ("light_cut", "ac_cut"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if not 0 <= self.work_start_hour < self.work_end_hour <= 24:
            raise ValueError("Working hours must satisfy 0 <= start < end <= 24")


def daily_energy(values_kw: np.ndarray, cal: Calendar) -> np.ndarray:
    """kWh per calendar day."""
    return np.bincount(cal.day_id, weights=np.asarray(values_kw, float), minlength=cal.n_days)


def low_use_hours(
    load_kw: np.ndarray, cal: Calendar, fraction: float = DsmDefaults.low_use_fraction
) -> np.ndarray:
    """Per-hour mask of low-use workdays: a Mon-Fri whose energy is below `fraction` of the median workday."""
    energy = daily_energy(load_kw, cal)
    weekend_day = np.zeros(cal.n_days, dtype=bool)
    weekend_day[cal.day_id] = cal.weekend
    median_workday = np.median(energy[~weekend_day])
    low_day = (~weekend_day) & (energy < fraction * median_workday)
    return low_day[cal.day_id]


def off_hours_mask(cal: Calendar, rules: DsmRules, low_use: np.ndarray | None = None) -> np.ndarray:
    """Hours in which the rules apply."""
    off = cal.weekend | (cal.hour < rules.work_start_hour) | (cal.hour >= rules.work_end_hour)
    if rules.low_use_as_holiday and low_use is not None:
        off = off | low_use
    return off


@dataclass(frozen=True)
class DsmResult:
    load_kw: np.ndarray
    saved_light_kw: np.ndarray
    saved_ac_kw: np.ndarray
    off_mask: np.ndarray

    @property
    def saved_kw(self) -> np.ndarray:
        return self.saved_light_kw + self.saved_ac_kw


def apply_rules(
    load_kw: np.ndarray,
    ac_kw: np.ndarray,
    light_kw: np.ndarray,
    off_mask: np.ndarray,
    rules: DsmRules,
) -> DsmResult:
    """Reduce lighting and air-conditioning in off-hours; plug loads are untouched."""
    saved_light = np.where(off_mask, np.asarray(light_kw, float) * rules.light_cut, 0.0)
    saved_ac = np.where(off_mask, np.asarray(ac_kw, float) * rules.ac_cut, 0.0)
    return DsmResult(np.asarray(load_kw, float) - saved_light - saved_ac, saved_light, saved_ac, off_mask)


# --------------------------------------------------------------------------- economics
@dataclass(frozen=True)
class Economics:
    """Cash flows and headline indicators of a project over the analysis horizon."""

    capex_thb: float
    om_year1_thb: float
    saving_year1_thb: float
    cashflows_thb: np.ndarray        # year 0 (negative capex) ... year N
    npv_thb: float
    irr: float | None
    payback_years: float | None      # simple payback; 0.0 when there is no capex

    @property
    def cumulative_thb(self) -> np.ndarray:
        return np.cumsum(self.cashflows_thb)

    @property
    def net_year1_thb(self) -> float:
        return self.saving_year1_thb - self.om_year1_thb


def _irr(cashflows: np.ndarray) -> float | None:
    """Internal rate of return by bisection; None when the flows never change sign."""
    if not (cashflows.min() < 0 < cashflows.max()):
        return None
    years = np.arange(len(cashflows))

    def npv(rate: float) -> float:
        return float(np.sum(cashflows / (1.0 + rate) ** years))

    low, high = -0.99, 10.0
    if npv(low) * npv(high) > 0:
        return None
    for _ in range(200):
        mid = 0.5 * (low + high)
        if npv(low) * npv(mid) <= 0:
            high = mid
        else:
            low = mid
    return 0.5 * (low + high)


def project_economics(
    capex_thb: float,
    pv_saving_thb: float,
    dsm_saving_thb: float,
    om_thb: float,
    fin: Finance = FINANCE,
) -> Economics:
    """Cash flows with the Excel model's conventions.

    * PV savings escalate with the tariff and fall with PV degradation.
    * Demand-side savings escalate with the tariff only (no degradation).
    * O&M escalates with the tariff.
    """
    years = np.arange(1, fin.horizon_years + 1)
    pv_path = pv_saving_thb * ((1 + fin.escalation) * (1 - fin.degradation)) ** (years - 1)
    dsm_path = dsm_saving_thb * (1 + fin.escalation) ** (years - 1)
    om_path = om_thb * (1 + fin.escalation) ** (years - 1)
    flows = np.concatenate(([-capex_thb], pv_path + dsm_path - om_path))

    discount = (1 + fin.discount_rate) ** np.arange(len(flows))
    net_year1 = pv_saving_thb + dsm_saving_thb - om_thb
    if capex_thb <= 0:
        payback = 0.0 if net_year1 > 0 else None
    else:
        payback = capex_thb / net_year1 if net_year1 > 0 else None
    return Economics(
        capex_thb=float(capex_thb),
        om_year1_thb=float(om_thb),
        saving_year1_thb=float(pv_saving_thb + dsm_saving_thb),
        cashflows_thb=flows,
        npv_thb=float(np.sum(flows / discount)),
        irr=_irr(flows),
        payback_years=payback,
    )
