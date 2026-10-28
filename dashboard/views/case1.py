"""Case 1: the building as we receive it (existing 20 kWp array)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import analytics, charts, components, theme
from ..components import CaseChip, Kpi
from ..config import PLANT
from ..context import Context
from ..fmt import kw, mwh, pct


def render(ctx: Context) -> None:
    d, r, cur = ctx.data, ctx.cases, ctx.cur
    cal, frame = d.calendar, d.frame
    c1, no_pv = r.case1, r.no_pv
    stats = analytics.load_stats(d.load_kw, cal.index)
    uses = analytics.category_energy(frame)
    existing_saving = no_pv.bill.total_thb - c1.bill.total_thb
    tone = theme.CASE_COLOR[1]

    components.page_header(
        CaseChip("Case 1 · Today", tone),
        "Case 1: the building as we receive it",
        "Measured 2019 hourly load of Chamchuri 5 with the existing 20 kWp array already on the roof. "
        "Everything else in the dashboard is measured against this case.",
    )

    components.kpi_row([
        Kpi("Annual energy", mwh(c1.load_kwh), f"Measured, {pct(d.filled_share)} of it gap-filled", tone),
        Kpi("Air conditioning", mwh(uses["Air conditioning"] * 1e3), f"**{pct(uses['Air conditioning'] / uses.sum(), 2)}** of the building's energy", tone),
        Kpi("Peak demand", kw(stats.peak_kw), stats.peak_time.strftime("%d %b %Y, %H:%M"), tone),
        Kpi("Annual electricity bill", cur.money(c1.bill.total_thb), cur.secondary(c1.bill.total_thb), tone),
        Kpi("Existing PV output", mwh(c1.pv_kwh), f"{PLANT.existing_kwp:g} kWp, estimated (±25%), not metered", theme.PV_OLD),
        Kpi("Saving from existing PV", cur.money(existing_saving), f"{pct(existing_saving / no_pv.bill.total_thb)} of the bill without PV", theme.PV_OLD),
        Kpi("Load factor", f"{stats.load_factor:.2f}", "average demand divided by peak demand", tone),
        Kpi("Lowest demand", kw(stats.minimum_kw), "night and weekend base load", tone),
    ])

    tabs = st.tabs(["Monthly energy", "Daily pattern", "Heat map", "End uses and floors", "Bill and duration"])

    with tabs[0]:
        table = analytics.monthly_table(
            {"Air conditioning": frame["ac_kw"].to_numpy(), "Lighting": frame["light_kw"].to_numpy(),
             "Plug loads": frame["plug_kw"].to_numpy()}, cal)
        components.show(charts.stacked_months(table, theme.END_USE, "Energy (MWh)", "MWh"), "c1_monthly")
        components.data_table(table.round(2), "c1_monthly", "case1_monthly_energy_mwh.csv")

    with tabs[1]:
        labels = analytics.day_type_labels(cal, r.low_use)
        workday = labels == analytics.DAY_TYPES[0]
        weekend = labels == analytics.DAY_TYPES[1]
        prof = analytics.hourly_profile
        series = {
            "Workday load": (prof(c1.load_kw, cal, workday), theme.LOAD, "solid"),
            "Weekend load": (prof(c1.load_kw, cal, weekend), theme.LOAD, "dot"),
            "Grid import, workdays": (prof(c1.grid_kw, cal, workday), theme.GRID, "solid"),
            "Existing PV (average day)": (prof(c1.pv_kw, cal, cal.hour >= 0), theme.PV_OLD, "solid"),
        }
        components.show(charts.profiles(series), "c1_profile")
        components.callout(
            "Workdays show two humps (morning and afternoon classes and offices) with a dip at lunch; weekends stay near "
            "the night base load. The existing array is small next to either.", "info",
        )

    with tabs[2]:
        view = st.radio("Group the hours by", ["Month", "Day of week"], horizontal=True, key="c1_heat")
        if view == "Month":
            z, xs = analytics.hour_by_month(c1.load_kw, cal), analytics.MONTH_LABELS
        else:
            z, xs = analytics.hour_by_weekday(c1.load_kw, cal), analytics.WEEKDAY_LABELS
        components.show(charts.heatmap(z, list(xs), theme.RAMP_BLUE, "kW"), "c1_heat_chart")

    with tabs[3]:
        a, b = st.columns(2)
        with a:
            st.markdown("**Share of annual energy by end use**")
            components.show(charts.donut(uses, theme.END_USE, f"{uses.sum():,.0f} MWh"), "c1_donut")
        with b:
            st.markdown("**Annual energy by floor**")
            components.show(charts.floor_bars(analytics.floor_energy(frame)), "c1_floors")

    with tabs[4]:
        a, b = st.columns(2)
        with a:
            st.markdown("**What the bill is made of**")
            m = c1.bill.monthly
            parts = pd.DataFrame({
                "Demand and service": m["demand_thb"] + m["service_thb"],
                "On-peak energy": m["energy_on_thb"],
                "Off-peak energy": m["energy_off_thb"] + m["export_credit_thb"],
            })
            components.show(charts.bill_parts_by_month(parts, cur), "c1_billparts")
        with b:
            st.markdown("**Load duration: hours at each demand level**")
            x0, y0 = analytics.duration_curve(no_pv.load_kw)
            x1, y1 = analytics.duration_curve(c1.grid_kw)
            components.show(charts.duration({"Building load": (x0, y0, theme.LOAD), "Grid import (Case 1)": (x1, y1, theme.GRID)}), "c1_duration")

    components.note_panels(
        applied=[
            "Measured 2019 hourly load, seven floors, split into air conditioning, lighting and plug loads (CU-BEMS dataset).",
            f"Existing array of **{PLANT.existing_kwp:g} kWp** using the south-facing Sheet_final profile (a typical day for each month).",
            "MEA Type 3.2 TOU tariff with Ft and VAT; on-peak is Monday to Friday, 09:00 to 22:00.",
        ],
        results=[
            f"The building uses **{mwh(c1.load_kwh)}** a year and peaks at **{kw(stats.peak_kw)}**.",
            f"Air conditioning is **{pct(uses['Air conditioning'] / uses.sum(), 2)}** of the energy, lighting {pct(uses['Lighting'] / uses.sum())}, plug loads {pct(uses['Plug loads'] / uses.sum())}.",
            f"The existing array supplies {pct(c1.pv_share_of_load)} of the load and saves {cur.money(existing_saving)} a year.",
        ],
        notes=[
            "Load factor is low: demand is concentrated in working hours, which is why off-hours rules have room to save.",
            "The tariff category is assumed; the real bill, Ft and 15-minute demand are still to be confirmed.",
            "Public holidays are treated as normal workdays, and demand uses hourly averages, so demand charges are slightly understated.",
        ],
    )
