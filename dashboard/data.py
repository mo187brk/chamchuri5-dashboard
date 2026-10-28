"""Load and validate the data files shipped in ./data."""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DATA_DIR, HOURS_PER_YEAR
from .engine import Calendar, build_calendar

N_FLOORS = 7
_REQUIRED_COLUMNS = [
    "datetime", "load_kw", "ac_kw", "light_kw", "plug_kw", "filled_kw",
    "pv_shape_existing", "pv_shape_new", *[f"floor{k}_kw" for k in range(1, N_FLOORS + 1)],
]


@dataclass(frozen=True)
class HourlyData:
    """The 8,760 hourly records plus their calendar."""

    frame: pd.DataFrame          # indexed by timestamp
    calendar: Calendar

    @property
    def load_kw(self) -> np.ndarray:
        return self.frame["load_kw"].to_numpy()

    @property
    def filled_share(self) -> float:
        """Share of building energy that was gap-filled by the dataset preparer."""
        return float(self.frame["filled_kw"].sum() / self.frame[[f"floor{k}_kw" for k in range(1, N_FLOORS + 1)]].sum().sum())


def validate_hourly(frame: pd.DataFrame) -> None:
    """Raise ValueError if the hourly table is not a clean, complete year."""
    missing = [c for c in _REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Hourly data is missing columns: {missing}")
    if len(frame) != HOURS_PER_YEAR:
        raise ValueError(f"Expected {HOURS_PER_YEAR} hourly rows, found {len(frame)}")
    numeric = frame.drop(columns=["datetime"])
    if numeric.isna().any().any():
        raise ValueError("Hourly data contains missing values")
    if (frame[["load_kw", "ac_kw", "light_kw", "plug_kw"]] < 0).any().any():
        raise ValueError("Hourly data contains negative loads")
    gap = (frame["ac_kw"] + frame["light_kw"] + frame["plug_kw"] - frame["load_kw"]).abs().max()
    if gap > 1e-3:
        raise ValueError(f"AC + lighting + plug does not add up to the building load (gap {gap:.3g} kW)")
    shapes = frame[["pv_shape_existing", "pv_shape_new"]]
    if (shapes < 0).any().any() or (shapes > 1.2).any().any():
        raise ValueError("PV profiles must be per-kWp values between 0 and 1.2")


def load_hourly() -> HourlyData:
    """Read, validate and index the hourly year."""
    frame = pd.read_csv(DATA_DIR / "hourly_2019.csv.gz", parse_dates=["datetime"])
    validate_hourly(frame)
    frame = frame.set_index("datetime")
    return HourlyData(frame, build_calendar(frame.index))


def load_sizing() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Static sizing sweeps (PV size, battery size) taken from the Excel model."""
    return (
        pd.read_csv(DATA_DIR / "sizing_pv.csv"),
        pd.read_csv(DATA_DIR / "sizing_battery.csv"),
    )


def load_reference() -> dict:
    """Headline results of the Excel model (used for cross-checks and the methodology page)."""
    return json.loads((DATA_DIR / "excel_reference.json").read_text(encoding="utf-8"))
