"""Case 2: Case 1 plus the new array on the free half of the roof."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from .. import analytics, charts, components, theme
from ..components import CaseChip, Kpi
from ..config import PLANT
from ..context import Context
from ..engine import NEW_ARRAY_AS_SUPPLIED, NEW_ARRAY_SOUTH
from ..fmt import kw, mwh, pct, years


def _orientation_table(ctx: Context) -> pd.DataFrame:
    """The same plant with the new array's profile as supplied and as a south-facing roof."""
    rows = {}
    for label, key in (("As supplied (Sheet_final)", NEW_ARRAY_AS_SUPPLIED), ("South-facing", NEW_ARRAY_SOUTH)):
        res = ctx.cases_for(new_array=key)
        eco = res.pv_economics
        rows[label] = [
            f"{res.pv_new_kw.sum() / PLANT.new_kwp:,.0f}",
            mwh(res.case2.pv_kwh),
            ctx.cur.money(res.pv_saving_thb),
            years(eco.payback_years),
            ctx.cur.money(eco.npv_thb),
        ]
    return pd.DataFrame(
        rows, index=["New array yield (kWh/kWp)", "Plant production", "Annual saving vs Case 1", "Simple payback", "NPV"]
    )


def render(ctx: Context) -> None:
    d, r, cur = ctx.data, ctx.cases, ctx.cur
    cal = d.calendar
    c1, c2, eco = r.case1, r.case2, r.pv_economics
    tone = theme.CASE_COLOR[2]
    new_kwh = float(r.pv_new_kw.sum())
    y_old = float(r.pv_existing_kw.sum()) / PLANT.existing_kwp
    y_new = new_kwh / PLANT.new_kwp
    peak_drop = c1.peak_onpeak_kw - c2.peak_onpeak_kw
    south = ctx.settings.new_array == NEW_ARRAY_SOUTH

    components.page_header(
        CaseChip("Case 2 · New solar", tone),
        "Case 2: a new array on the free half of the roof",
        f"A new {PLANT.new_kwp:g} kWp array ({round(PLANT.new_kwp / 0.55)} modules of 550 W) joins the existing "
        f"{PLANT.existing_kwp:g} kWp, for {PLANT.existing_kwp + PLANT.new_kwp:g} kWp in total.",
    )

    components.kpi_row([
        Kpi("Plant production", mwh(c2.pv_kwh), f"existing {mwh(c1.pv_kwh)} + new {mwh(new_kwh)}", tone),
        Kpi("Share of building energy", pct(c2.pv_share_of_load), f"existing array alone: {pct(c1.pv_share_of_load)}", tone),
        Kpi("Used inside the building", pct(c2.self_consumption, 3), f"{c2.export_kwh:,.1f} kWh exported in a year", tone),
        Kpi("Saving vs Case 1", cur.money(r.pv_saving_thb), f"{cur.secondary(r.pv_saving_thb)} per year", tone,
            delta=f"{pct(r.pv_saving_thb / c1.bill.total_thb)} of the bill"),
        Kpi("Investment (new array)", cur.money(eco.capex_thb), f"{PLANT.new_kwp:g} kWp at {cur.money(ctx.settings.pv_cost_per_kwp, 1)}/kWp (assumed)", tone),
        Kpi("Simple payback", years(eco.payback_years), f"net of {cur.money(eco.om_year1_thb)} a year O&M", tone),
        Kpi("NPV and IRR", cur.money(eco.npv_thb), f"IRR {pct(eco.irr)} over {len(eco.cashflows_thb) - 1} years" if eco.irr is not None else "IRR not defined", tone),
        Kpi("Billed on-peak demand", kw(c2.peak_onpeak_kw), f"{peak_drop:,.1f} kW below Case 1", tone,
            delta=f"-{pct(peak_drop / c1.peak_onpeak_kw)}", ),
    ])

    if y_new < 0.95 * y_old and not south:
        components.callout(
            f"**The new array yields {pct(1 - y_new / y_old, 0)} less per kWp than the existing one** "
            f"({y_new:,.0f} against {y_old:,.0f} kWh/kWp). The Sheet_final profile was entered with azimuth 0, "
            "which is north if it follows the Global Solar Atlas convention. Check the Orientation tab and the real roof layout.",
            "warn",
        )

    tabs = st.tabs(["Production", "One week", "Grid import", "Cash flow", "Orientation check"])

    with tabs[0]:
        a, b = st.columns([1.2, 1])
        with a:
            table = analytics.monthly_table({"Existing array": r.pv_existing_kw, "New array": r.pv_new_kw}, cal)
            components.show(charts.stacked_months(table, {"Existing array": theme.PV_OLD, "New array": theme.PV_NEW}, "Energy (MWh)", "MWh"), "c2_prod")
        with b:
            z = analytics.hour_by_month(c2.pv_kw, cal)
            components.show(charts.heatmap(z, analytics.MONTH_LABELS, theme.RAMP_AMBER, "kW"), "c2_pvheat")
        components.data_table(table.round(2), "c2_prod", "case2_monthly_pv_mwh.csv")

    with tabs[1]:
        start = st.date_input("Week starting", value=date(2019, 4, 22), min_value=date(2019, 1, 1),
                              max_value=date(2019, 12, 25), key="c2_week")
        pos = int(np.searchsorted(cal.index.values, np.datetime64(start)))
        sl = slice(pos, pos + 168)
        fig = charts.week(cal.index[sl], c2.load_kw[sl], r.pv_existing_kw[sl], r.pv_new_kw[sl], c2.grid_kw[sl], cal.weekend[sl])
        components.show(fig, "c2_week_chart")
        components.callout(
            "Every day shows the same bell: the PV profile is a typical day for each month, so cloudy days are not modelled. "
            "Weekends are shaded; the plant never exceeds the load, which is why nothing is exported.", "info",
        )

    with tabs[2]:
        table = analytics.monthly_table({"Case 1 · Today": c1.grid_kw, "Case 2 · New solar": c2.grid_kw}, cal)
        components.show(charts.grouped_months(table, {"Case 1 · Today": theme.CASE_COLOR[1], "Case 2 · New solar": theme.CASE_COLOR[2]}, "Grid import (MWh)", "MWh"), "c2_grid")
        components.data_table(table.round(2), "c2_grid", "case2_grid_import_mwh.csv")

    with tabs[3]:
        components.show(charts.cumulative_cashflow(eco, cur, "New array", tone), "c2_cash")
        components.callout(
            "Savings grow with the tariff (2% a year) and shrink with PV degradation (0.5% a year); O&M grows with the tariff. "
            "Prices are placeholders: change the PV price in the sidebar to see how robust the payback is.", "info",
        )

    with tabs[4]:
        st.markdown("**Does the new array face south?** The same plant with the profile as supplied and with the south-facing profile of the existing array.")
        components.table(_orientation_table(ctx))
        st.caption("Switch the orientation for the whole dashboard in the sidebar.")

    components.section("A word on batteries")
    bat = ctx.sizing_battery
    row = bat[(bat["battery_kwh"] == 200) & (bat["power_kw"] == 100)]
    if len(row):
        b = row.iloc[0]
        components.callout(
            f"The Excel study also tried a 200 kWh / 100 kW battery on top of this plant: it adds "
            f"{cur.money(b['extra_saving_thb'])} a year but its NPV is {cur.money(b['npv_thb'])}. It would pay back only below about "
            f"{cur.money(b['breakeven_thb_per_kwh'], 1)} per kWh installed (14,000 THB/kWh assumed), so it is left out of the cases.", "info",
        )

    components.note_panels(
        applied=[
            f"New array of **{PLANT.new_kwp:g} kWp** (135 modules of 550 W) added to the existing {PLANT.existing_kwp:g} kWp; the old array stays.",
            f"Installed price {cur.money(ctx.settings.pv_cost_per_kwp, 1)}/kWp and O&M 260 THB/kWp/year, both assumed.",
            f"Profile of the new array: **{'south-facing (same as the existing array)' if south else 'as supplied in Sheet_final'}**.",
        ],
        results=[
            f"The plant produces **{mwh(c2.pv_kwh)}**, {pct(c2.pv_share_of_load)} of the building's energy.",
            f"The bill falls by **{cur.money(r.pv_saving_thb)}** a year; simple payback {years(eco.payback_years)}, NPV {cur.money(eco.npv_thb)}.",
            f"Billed on-peak demand drops by {peak_drop:,.1f} kW.",
        ],
        notes=[
            "No weather variability: a typical day per month overstates how reliably PV cuts the peak, so the demand-charge part of the saving is the fragile part.",
            "The existing array is estimated, not metered; the new array's orientation is unconfirmed.",
            "Prices, discount rate and escalation are assumptions until quotes and finance inputs arrive.",
        ],
    )
