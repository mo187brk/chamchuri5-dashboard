"""Descriptive statistics and table shaping for the charts (pandas only, no plotting)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .engine import MONTH_LABELS, Calendar, DsmRules, apply_rules, off_hours_mask, simulate

DAY_TYPES = ("Regular workdays", "Weekends", "Low-use workdays")
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass(frozen=True)
class LoadStats:
    energy_mwh: float
    peak_kw: float
    peak_time: pd.Timestamp
    average_kw: float
    minimum_kw: float
    load_factor: float


def load_stats(load_kw: np.ndarray, index: pd.DatetimeIndex) -> LoadStats:
    """Headline statistics of an hourly load series."""
    peak_pos = int(np.argmax(load_kw))
    return LoadStats(
        energy_mwh=float(load_kw.sum() / 1e3),
        peak_kw=float(load_kw[peak_pos]),
        peak_time=index[peak_pos],
        average_kw=float(load_kw.mean()),
        minimum_kw=float(load_kw.min()),
        load_factor=float(load_kw.mean() / load_kw[peak_pos]),
    )


def month_sums(values_kw: np.ndarray, cal: Calendar, scale: float = 1e3) -> np.ndarray:
    """Monthly energy (MWh by default) from hourly kW."""
    return np.add.reduceat(np.asarray(values_kw, float), cal.month_starts) / scale


def monthly_table(columns_kw: dict[str, np.ndarray], cal: Calendar) -> pd.DataFrame:
    """Monthly energy in MWh for several hourly series."""
    return pd.DataFrame(
        {name: month_sums(values, cal) for name, values in columns_kw.items()},
        index=pd.Index(MONTH_LABELS, name="month"),
    )


def day_type_labels(cal: Calendar, low_use: np.ndarray) -> np.ndarray:
    """Per-hour label: weekend, low-use workday or regular workday."""
    labels = np.full(cal.n_hours, DAY_TYPES[0], dtype=object)
    labels[low_use] = DAY_TYPES[2]
    labels[cal.weekend] = DAY_TYPES[1]
    return labels


def day_type_counts(cal: Calendar, labels: np.ndarray) -> dict[str, int]:
    """Number of calendar days of each type."""
    return {name: int((labels == name).sum() // 24) for name in DAY_TYPES}


def hourly_profile(values_kw: np.ndarray, cal: Calendar, mask: np.ndarray) -> np.ndarray:
    """Average kW for each hour of the day over the selected hours (length 24)."""
    selected_hours = cal.hour[mask]
    sums = np.bincount(selected_hours, weights=np.asarray(values_kw, float)[mask], minlength=24)
    counts = np.bincount(selected_hours, minlength=24)
    return sums / np.maximum(counts, 1)


def hour_by_month(values_kw: np.ndarray, cal: Calendar) -> np.ndarray:
    """Average kW matrix [24 hours x 12 months]."""
    out = np.zeros((24, 12))
    values = np.asarray(values_kw, float)
    for m in range(12):
        out[:, m] = hourly_profile(values, cal, cal.month == m + 1)
    return out


def hour_by_weekday(values_kw: np.ndarray, cal: Calendar) -> np.ndarray:
    """Average kW matrix [24 hours x 7 weekdays, Monday first]."""
    out = np.zeros((24, 7))
    values = np.asarray(values_kw, float)
    weekday = cal.index.dayofweek.to_numpy()
    for d in range(7):
        out[:, d] = hourly_profile(values, cal, weekday == d)
    return out


def duration_curve(values_kw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Percent of the year (x) and the load that is exceeded for that long (y)."""
    ordered = np.sort(np.asarray(values_kw, float))[::-1]
    return np.linspace(0, 100, len(ordered)), ordered


def category_energy(frame: pd.DataFrame) -> pd.Series:
    """Annual MWh by end use."""
    return pd.Series(
        {
            "Air conditioning": frame["ac_kw"].sum() / 1e3,
            "Lighting": frame["light_kw"].sum() / 1e3,
            "Plug loads": frame["plug_kw"].sum() / 1e3,
        }
    )


def floor_energy(frame: pd.DataFrame, n_floors: int = 7) -> pd.Series:
    """Annual MWh by floor, floor 1 first."""
    return pd.Series(
        {f"Floor {k}": frame[f"floor{k}_kw"].sum() / 1e3 for k in range(1, n_floors + 1)}
    )


def typical_day_by_month(values_kw: np.ndarray, cal: Calendar, month: int, mask: np.ndarray | None = None) -> np.ndarray:
    """Average 24-hour profile of one month (optionally limited to a mask)."""
    selected = cal.month == month
    if mask is not None:
        selected = selected & mask
    return hourly_profile(values_kw, cal, selected)


def sweep_savings(
    load_kw: np.ndarray,
    ac_kw: np.ndarray,
    light_kw: np.ndarray,
    pv_kw: np.ndarray,
    cal: Calendar,
    base_bill_thb: float,
    light_cuts: list[float],
    ac_cuts: list[float],
    low_use: np.ndarray,
    low_use_as_holiday: bool,
) -> pd.DataFrame:
    """Annual bill saving (THB, against `base_bill_thb`) for a grid of lighting and AC cuts."""
    out = pd.DataFrame(index=[f"{int(round(100 * y))}%" for y in ac_cuts],
                       columns=[f"{int(round(100 * x))}%" for x in light_cuts], dtype=float)
    for y in ac_cuts:
        for x in light_cuts:
            rules = DsmRules(light_cut=x, ac_cut=y, low_use_as_holiday=low_use_as_holiday)
            res = apply_rules(load_kw, ac_kw, light_kw, off_hours_mask(cal, rules, low_use), rules)
            bill = simulate(res.load_kw, pv_kw, cal).bill.total_thb
            out.loc[f"{int(round(100 * y))}%", f"{int(round(100 * x))}%"] = base_bill_thb - bill
    out.index.name = "AC cut"
    out.columns.name = "Lighting cut"
    return out
