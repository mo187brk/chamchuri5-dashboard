"""Shared state handed to every page: data, live settings, results and display currency."""

from __future__ import annotations

from dataclasses import astuple, dataclass, replace

import pandas as pd
import streamlit as st

from . import case4 as case4_mod
from . import data as data_mod
from .data import HourlyData
from .fmt import Currency
from .model import CaseResults, Settings, run_cases


@st.cache_resource(show_spinner="Loading the 2019 hourly data...")
def get_data() -> HourlyData:
    """Read and validate the shipped hourly year once per server process."""
    return data_mod.load_hourly()


@st.cache_resource(show_spinner=False, max_entries=32)
def _cached_cases(_data: HourlyData, settings_key: tuple) -> CaseResults:
    """Cached simulation. The key is a plain tuple so hashing never depends on the dataclass type."""
    return run_cases(_data, Settings(*settings_key))


def get_cases(data: HourlyData, settings: Settings) -> CaseResults:
    """Simulate Cases 1-3 for one set of settings (cached per distinct settings)."""
    return _cached_cases(data, astuple(settings))


@st.cache_resource(show_spinner=False, max_entries=32)
def _cached_case4(_data: HourlyData, settings_key: tuple) -> case4_mod.Case4Results:
    """Cached Case 4 simulation for one set of settings."""
    settings = Settings(*settings_key)
    return case4_mod.run_case4(_data, get_cases(_data, settings), settings)


def get_case4(data: HourlyData, settings: Settings) -> case4_mod.Case4Results:
    """Case 4 for one set of settings (cached per distinct settings)."""
    return _cached_case4(data, astuple(settings))


@dataclass(frozen=True)
class Context:
    data: HourlyData
    settings: Settings
    cur: Currency
    cases: CaseResults
    sizing_pv: pd.DataFrame
    sizing_battery: pd.DataFrame
    reference: dict

    def cases_for(self, **changes) -> CaseResults:
        """Results for the current settings with some fields changed (e.g. the other array orientation)."""
        return get_cases(self.data, replace(self.settings, **changes))

    @property
    def case4(self) -> case4_mod.Case4Results:
        """Case 4 for the current settings (needs the plant data in ./data)."""
        return get_case4(self.data, self.settings)
