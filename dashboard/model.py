"""Orchestration: turn the hourly data and the user's settings into the three live cases.

Case 1  Today: the building with the existing 20 kWp array.
Case 2  Case 1 plus the new array on the free half of the roof.
Case 3  Case 2 plus the off-hours lighting and air-conditioning rules.
Case 4  What-if: an off-site plant whose energy is credited on the bill (see case4.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import DSM, FINANCE, PLANT, TARIFF, Finance, Plant, Tariff
from .data import HourlyData
from .engine import (
    NEW_ARRAY_AS_SUPPLIED,
    DsmResult,
    DsmRules,
    Economics,
    Scenario,
    apply_rules,
    low_use_hours,
    off_hours_mask,
    project_economics,
    pv_output,
    simulate,
)


@dataclass(frozen=True)
class Settings:
    """Everything the user can change from the interface."""

    new_array: str = NEW_ARRAY_AS_SUPPLIED
    light_cut: float = 0.40
    ac_cut: float = 0.25
    low_use_as_holiday: bool = False
    pv_cost_per_kwp: float = FINANCE.pv_cost_per_kwp
    dsm_cost_thb: float = 0.0
    work_start_hour: int = DSM.work_start_hour   # rules apply before this hour on workdays
    work_end_hour: int = DSM.work_end_hour       # ... and from this hour on
    c4_credit: float = TARIFF.export_price       # THB/kWh credited on the bill for the Case 4 plant's output

    @property
    def rules(self) -> DsmRules:
        return DsmRules(
            light_cut=self.light_cut,
            ac_cut=self.ac_cut,
            work_start_hour=self.work_start_hour,
            work_end_hour=self.work_end_hour,
            low_use_as_holiday=self.low_use_as_holiday,
        )


@dataclass(frozen=True)
class CaseResults:
    """All simulated scenarios and project economics for one set of settings."""

    pv_existing_kw: np.ndarray
    pv_new_kw: np.ndarray
    no_pv: Scenario            # reference only: the building with no solar at all
    case1: Scenario
    case2: Scenario
    case3: Scenario
    dsm: DsmResult
    low_use: np.ndarray        # hours that belong to low-use workdays
    pv_economics: Economics    # new array alone, against Case 1
    dsm_economics: Economics   # rules alone, against Case 2
    total_economics: Economics # new array + rules, against Case 1

    @property
    def pv_saving_thb(self) -> float:
        return self.case1.bill.total_thb - self.case2.bill.total_thb

    @property
    def dsm_saving_thb(self) -> float:
        return self.case2.bill.total_thb - self.case3.bill.total_thb

    @property
    def total_saving_thb(self) -> float:
        return self.case1.bill.total_thb - self.case3.bill.total_thb


def run_cases(
    data: HourlyData,
    settings: Settings = Settings(),
    plant: Plant = PLANT,
    fin: Finance = FINANCE,
    tariff: Tariff = TARIFF,
) -> CaseResults:
    """Simulate Cases 1-3 and compute their economics."""
    cal = data.calendar
    frame = data.frame
    load = frame["load_kw"].to_numpy()

    pv_old, pv_new = pv_output(
        frame["pv_shape_existing"].to_numpy(),
        frame["pv_shape_new"].to_numpy(),
        plant.existing_kwp,
        plant.new_kwp,
        settings.new_array,
    )

    no_pv = simulate(load, np.zeros_like(load), cal, tariff)
    case1 = simulate(load, pv_old, cal, tariff)
    case2 = simulate(load, pv_old + pv_new, cal, tariff)

    low_use = low_use_hours(load, cal)
    rules = settings.rules
    dsm = apply_rules(
        load,
        frame["ac_kw"].to_numpy(),
        frame["light_kw"].to_numpy(),
        off_hours_mask(cal, rules, low_use),
        rules,
    )
    case3 = simulate(dsm.load_kw, pv_old + pv_new, cal, tariff)

    pv_capex = plant.new_kwp * settings.pv_cost_per_kwp
    pv_om = plant.new_kwp * fin.pv_om_per_kwp
    pv_saving = case1.bill.total_thb - case2.bill.total_thb
    dsm_saving = case2.bill.total_thb - case3.bill.total_thb

    return CaseResults(
        pv_existing_kw=pv_old,
        pv_new_kw=pv_new,
        no_pv=no_pv,
        case1=case1,
        case2=case2,
        case3=case3,
        dsm=dsm,
        low_use=low_use,
        pv_economics=project_economics(pv_capex, pv_saving, 0.0, pv_om, fin),
        dsm_economics=project_economics(settings.dsm_cost_thb, 0.0, dsm_saving, 0.0, fin),
        total_economics=project_economics(
            pv_capex + settings.dsm_cost_thb, pv_saving, dsm_saving, pv_om, fin
        ),
    )
