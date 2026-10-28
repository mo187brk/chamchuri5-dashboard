"""Case 4 (what-if): an off-site plant whose output is credited against the building's bill."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from .. import analytics, case4, charts, components, theme
from ..components import CaseChip, Kpi
from ..config import GRID, PLANT, TARIFF
from ..context import Context
from ..fmt import kw, mwh, pct, years


# --------------------------------------------------------------------------- fallback when the data is missing
def _sizing_preview(ctx: Context) -> None:
    """Static snapshot of the Excel sizing sweep (a plant behind the meter), shown only if the plant data is missing."""
    cur, df = ctx.cur, ctx.sizing_pv
    total_now = PLANT.existing_kwp + PLANT.new_kwp
    st.caption("Static snapshot of the Excel sizing sweep (same tariff and prices, no battery, plant behind the meter). It is not live and ignores roof space.")
    a, b = st.columns(2)
    with a:
        st.markdown("**Annual saving against today**")
        components.show(charts.sizing_line(df, "saving_thb", f"{cur.unit} thousand per year", lambda v: cur.to_display(v) / 1e3,
                                           theme.PV_NEW, f"{cur.unit}k", total_now), "c4_saving")
    with b:
        st.markdown("**NPV over 20 years**")
        components.show(charts.sizing_line(df, "npv_thb", f"{cur.unit} million", lambda v: cur.to_display(v) / 1e6,
                                           theme.SAVE, f"{cur.unit}M", total_now), "c4_npv")


def _waiting_page(ctx: Context) -> None:
    components.page_header(
        CaseChip("Case 4 · What-if (soon)", theme.CASE_COLOR[4], live=False),
        "Case 4: what if the plant sat on other land?",
        "A larger solar plant off the roof, with its energy credited against the building's bill. This case waits for the plant data.",
    )
    components.callout(
        "**The plant data was not found.** Expected `data/case4_plant.json` and `data/case4_plant_profile.csv` "
        "(or the hourly file `data/case4_expanded.csv`). Below is a preview from the Excel sizing sweep.", "warn",
    )
    components.section("Preview: what a bigger plant would do")
    _sizing_preview(ctx)


# --------------------------------------------------------------------------- tables
def _money_table(ctx: Context, c4: case4.Case4Results) -> pd.DataFrame:
    """The two economic views side by side."""
    cur = ctx.cur
    rows = {}
    for label, eco, saving in (
        ("Building the plant (against Case 3)", c4.vs_case3, c4.saving_vs_case3_thb),
        ("Whole programme (against Case 1)", c4.vs_case1, c4.saving_vs_case1_thb),
    ):
        rows[label] = [
            cur.money(eco.capex_thb), cur.money(saving), cur.money(eco.om_year1_thb),
            years(eco.payback_years), cur.money(eco.npv_thb), pct(eco.irr) if eco.irr is not None else "n/a",
        ]
    return pd.DataFrame(rows, index=["Investment", "Annual saving", "O&M per year", "Simple payback", "NPV", "IRR"])


def _credit_table(ctx: Context, c4: case4.Case4Results) -> pd.DataFrame:
    """Three ways of crediting the plant's energy, formatted for display."""
    raw = case4.credit_options(ctx.data, ctx.cases, c4, ctx.settings)
    cur = ctx.cur
    return pd.DataFrame(
        {
            "Credit earned": [cur.money(v) for v in raw["Credit earned"]],
            "Saving vs Case 3": [cur.money(v) for v in raw["Saving vs Case 3"]],
            "Payback of the plant": [years(v) for v in raw["Payback (years)"]],
            "NPV of the plant": [cur.money(v) for v in raw["NPV"]],
        },
        index=raw.index,
    )


# --------------------------------------------------------------------------- page
def render(ctx: Context) -> None:
    if not case4.plant_available():
        _waiting_page(ctx)
        return
    try:
        c4 = ctx.case4
    except ValueError as exc:
        components.page_header(CaseChip("Case 4 · What-if", theme.CASE_COLOR[4], live=False),
                               "Case 4: what if the plant sat on other land?", "The plant data could not be used.")
        components.callout(f"**The Case 4 data is not valid:** {exc}", "warn")
        return

    d, r, cur, s = ctx.data, ctx.cases, ctx.cur, ctx.settings
    cal = d.calendar
    spec, sc = c4.spec, c4.scenario
    tone = theme.CASE_COLOR[4]
    eco3 = c4.vs_case3
    capex_per_kwp = cur.money(s.pv_cost_per_kwp, 1)

    components.page_header(
        CaseChip("Case 4 · What-if", tone),
        "Case 4: what if the plant sat on other land?",
        f"A hypothetical {spec.capacity_kwp:g} kWp plant ({spec.modules:,} modules of {spec.module_kw * 1000:.0f} W, tilted "
        f"{spec.tilt_deg:g}° to the south) feeds the grid, and its energy is credited against the Chamchuri 5 bill.",
    )
    components.callout(
        "**A what-if, not a project.** The roof has no room for more panels. Suppose instead that open land were found, a "
        f"{spec.capacity_kwp:g} kWp plant were built there, all of its output were sent to the grid, and the credit were "
        "deducted from the building's electricity bill (virtual net metering). The roof arrays of Cases 2-3 stay as they are. "
        "The site, the legal basis, the credit price and the cost are all assumptions.", "warn",
    )

    options = case4.credit_options(d, r, c4, s)
    buyback_payback = options["Payback (years)"].iloc[1]
    retail_payback = options["Payback (years)"].iloc[2]
    components.kpi_row([
        Kpi("Plant output", mwh(c4.plant_kwh), f"{spec.capacity_kwp:g} kWp · {c4.source}", tone),
        Kpi("Building energy offset", pct(c4.offset_share), "credited on the bill, not used directly", tone),
        Kpi("Credit earned", cur.money(c4.export_revenue_thb), f"at {c4.credit:.2f} THB/kWh (set in the sidebar)", tone),
        Kpi("Annual electricity bill", cur.money(sc.bill.total_thb), f"Case 3: {cur.money(c4.bill_case3_thb)}", tone),
        Kpi("Saving vs Case 3", cur.money(c4.saving_vs_case3_thb), f"{cur.secondary(c4.saving_vs_case3_thb)} per year", tone,
            delta=f"{pct(c4.saving_vs_case3_thb / c4.bill_case3_thb)} of the Case 3 bill"),
        Kpi("Saving vs Case 1", cur.money(c4.saving_vs_case1_thb), f"{pct(c4.saving_vs_case1_thb / c4.bill_case1_thb)} of today's bill", tone),
        Kpi("Investment (plant)", cur.money(eco3.capex_thb), f"{spec.capacity_kwp:g} kWp at {capex_per_kwp}/kWp, assumed; land and grid connection excluded", tone),
        Kpi("Simple payback", years(eco3.payback_years), f"net of {cur.money(eco3.om_year1_thb)} a year O&M", tone),
        Kpi("NPV and IRR", cur.money(eco3.npv_thb),
            f"IRR {pct(eco3.irr)} over {len(eco3.cashflows_thb) - 1} years" if eco3.irr is not None else "IRR not defined", tone),
        Kpi("Largest export", kw(c4.peak_export_kw), f"transformer carries about {kw(GRID.limit_kw, 0)} (assumed)", tone,
            delta="above the limit" if c4.exceeds_transformer else "", delta_warn=c4.exceeds_transformer),
        Kpi("Billed on-peak demand", kw(sc.peak_onpeak_kw), "unchanged: the plant is off-site, so the building still draws the same peak", tone),
        Kpi("Land needed", f"{c4.module_area_needed_m2:,.0f} m²", f"modules alone, about {spec.module_area_m2:g} m² each; more with row spacing", tone),
    ])

    components.callout(
        f"**The credit price decides whether this works.** At the Thai buy-back ({TARIFF.export_price:g} THB/kWh) the plant pays back in "
        f"{years(buyback_payback).lower()}; if every kWh were credited at the building's own retail price it would take "
        f"{years(retail_payback).lower()}. With no credit it never pays back.", "info",
    )

    tabs = st.tabs(["Output and credit", "Typical days", "One week", "Value of the credit", "Cash flow"])

    with tabs[0]:
        a, b = st.columns([1.2, 1])
        with a:
            st.markdown("**Energy each month: roof arrays and the off-site plant**")
            table = analytics.monthly_table(
                {"Roof arrays, used in the building": sc.used_kw, "Off-site plant, credited": c4.plant_kw}, cal)
            components.show(charts.stacked_months(
                table, {"Roof arrays, used in the building": theme.PV_NEW, "Off-site plant, credited": theme.SAVE},
                "Energy (MWh)", "MWh"), "c4_months")
        with b:
            st.markdown("**When the plant produces (average kW, hour by month)**")
            components.show(charts.heatmap(analytics.hour_by_month(c4.plant_kw, cal), analytics.MONTH_LABELS, theme.RAMP_TEAL, "kW"), "c4_plantheat")
        components.data_table(table.round(2), "c4_months", "case4_monthly_energy_mwh.csv")

    with tabs[1]:
        labels = analytics.day_type_labels(cal, r.low_use)
        counts = analytics.day_type_counts(cal, labels)
        prof = analytics.hourly_profile
        panels = []
        for name in analytics.DAY_TYPES:
            mask = labels == name
            panels.append((
                f"{name} ({counts[name]} days)",
                {
                    "Building load (after rules)": (prof(sc.load_kw, cal, mask), theme.LOAD, "dash"),
                    "Roof PV": (prof(c4.roof_pv_kw, cal, mask), theme.PV_NEW, "solid"),
                    "Grid import": (prof(sc.grid_kw, cal, mask), theme.GRID, "solid"),
                    "Off-site plant (credited)": (prof(c4.plant_kw, cal, mask), theme.SAVE, "solid"),
                },
            ))
        components.show(charts.day_type_panels(panels), "c4_daytypes")
        components.callout(
            "The grid import does not move: the plant is not behind the meter, so the building keeps buying what it needs and "
            "is paid back afterwards, hour by hour or at a flat price. That is why the billed demand stays the same.", "info",
        )

    with tabs[2]:
        start = st.date_input("Week starting", value=date(2019, 4, 27), min_value=date(2019, 1, 1),
                              max_value=date(2019, 12, 25), key="c4_week")
        pos = int(np.searchsorted(cal.index.values, np.datetime64(start)))
        sl = slice(pos, pos + 168)
        fig = charts.week(cal.index[sl], sc.load_kw[sl], c4.roof_pv_kw[sl], c4.plant_kw[sl], sc.grid_kw[sl], cal.weekend[sl],
                          names=("Roof arrays", "Off-site plant"), export=sc.export_kw[sl])
        components.show(fig, "c4_week_chart")
        components.callout("The default week starts on a Saturday so that weekend and workdays sit side by side. "
                           "Every day shows the same bell because the profile is a typical day for each month.", "info")

    with tabs[3]:
        st.markdown("**The same plant under three ways of crediting its energy**")
        components.table(_credit_table(ctx, c4))
        curve = case4.credit_curve(c4, s)
        marks = {"No credit": 0.0, f"Buy-back {TARIFF.export_price:g}": TARIFF.export_price, "Retail on-peak": round(TARIFF.on_peak_rate, 2)}
        components.show(charts.credit_payback(curve, marks, c4.credit), "c4_credit_curve")
        components.callout(
            "The dashed line is the credit set in the sidebar. **The retail TOU price is an upper bound:** it assumes every kWh from "
            "the plant is worth what the building pays for a kWh in that hour, with no wheeling or administration charge. The legal "
            "basis of virtual net metering in Thailand, and the price it would pay, still have to be confirmed.", "warn",
        )

    with tabs[4]:
        components.show(charts.cumulative_cashflow(eco3, cur, "Off-site plant", tone), "c4_cash")
        components.table(_money_table(ctx, c4))
        st.caption("Building the plant compares Case 4 with Case 3; the whole programme compares it with today's building, "
                   "with the new roof array and the cost of the rules (sidebar) included.")

    components.section("Where Case 4 sits", "Annual electricity bill of every case, in " + cur.unit + ".")
    fig = charts.bill_by_case(
        ["No PV", "Case 1", "Case 2", "Case 3", "Case 4"],
        [r.no_pv.bill.total_thb, r.case1.bill.total_thb, r.case2.bill.total_thb, r.case3.bill.total_thb, sc.bill.total_thb],
        [theme.MUTED, theme.CASE_COLOR[1], theme.CASE_COLOR[2], theme.CASE_COLOR[3], tone], cur,
    )
    components.show(fig, "c4_bills")

    components.note_panels(
        applied=[
            f"A **{spec.capacity_kwp:g} kWp** plant on other land: {spec.modules:,} modules of {spec.module_kw * 1000:.0f} W, tilt "
            f"{spec.tilt_deg:g}°, south-facing, PVGIS losses {spec.losses_pct:g}%. Output is the typical day of each month ({c4.source}).",
            "Its whole output goes to the grid and is credited on the building's bill. The roof arrays and the rules of Case 3 stay as they are.",
            f"Credit **{c4.credit:.2f} THB/kWh** (sidebar). Investment at {capex_per_kwp}/kWp, the Case 2 price.",
        ],
        results=[
            f"The plant makes **{mwh(c4.plant_kwh)}**, equal to {pct(c4.offset_share)} of the building's yearly energy.",
            f"At {c4.credit:.2f} THB/kWh it earns **{cur.money(c4.export_revenue_thb)}** a year; the bill falls to {cur.money(sc.bill.total_thb)}.",
            f"Building it pays back in {years(eco3.payback_years).lower()} (NPV {cur.money(eco3.npv_thb)}); with credit at the retail price, "
            f"{years(retail_payback).lower()}.",
        ],
        notes=[
            "Hypothetical: no site, permit, grid connection or net-metering agreement exists. The credit is a scenario, not a fact.",
            "Not included: land or roof rent, grid-connection works, wheeling or administration charges, and any limit on how much can be credited.",
            "Typical-day profile with no weather variability, the same shape as the existing array. The price per kWp is the Case 2 placeholder; "
            f"a {spec.capacity_kwp:g} kWp plant would probably cost less per kWp.",
        ],
    )
