"""Overview: the four cases side by side."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import case4, charts, components, theme
from ..components import CaseChip
from ..config import PLANT
from ..context import Context
from ..fmt import kw, mwh, pct, years


def chips(ctx: Context) -> dict[int, CaseChip]:
    """Case chips shared by the hero and the cards; Case 4 turns live when its data file exists."""
    live4 = case4.plant_available()
    return {
        1: CaseChip("Case 1 · Today", theme.CASE_COLOR[1]),
        2: CaseChip("Case 2 · New solar", theme.CASE_COLOR[2]),
        3: CaseChip("Case 3 · Solar + rules", theme.CASE_COLOR[3]),
        4: CaseChip("Case 4 · What-if" + ("" if live4 else " (soon)"), theme.CASE_COLOR[4], live=live4),
    }


def summary_table(ctx: Context) -> pd.DataFrame:
    """One column per case, one row per headline indicator."""
    r, cur = ctx.cases, ctx.cur
    base = r.case1.bill.total_thb

    def money(v: float) -> str:
        return cur.money(v)

    def row(s) -> list[str]:
        return [
            money(s.bill.total_thb),
            money(base - s.bill.total_thb),
            mwh(s.grid_kwh),
            mwh(s.pv_kwh),
            pct(s.pv_share_of_load),
            kw(s.peak_onpeak_kw),
        ]

    columns = {
        "No PV (reference)": row(r.no_pv),
        "Case 1 · Today": row(r.case1),
        "Case 2 · New solar": row(r.case2),
        "Case 3 · Solar + rules": row(r.case3),
    }
    capex = ["-", "-", money(r.pv_economics.capex_thb), money(r.total_economics.capex_thb)]
    payback = ["-", "-", years(r.pv_economics.payback_years), years(r.total_economics.payback_years)]
    npv = ["-", "-", money(r.pv_economics.npv_thb), money(r.total_economics.npv_thb)]
    if case4.plant_available():
        c4 = ctx.case4
        columns["Case 4 · What-if"] = row(c4.scenario)
        capex.append(money(c4.vs_case1.capex_thb))
        payback.append(years(c4.vs_case1.payback_years))
        npv.append(money(c4.vs_case1.npv_thb))
    table = pd.DataFrame(
        columns,
        index=[
            "Annual electricity bill", "Saving vs Case 1", "Grid import", "PV production",
            "PV share of building load", "Billed on-peak demand",
        ],
    )
    table.loc["Added investment (vs Case 1)"] = capex
    table.loc["Simple payback"] = payback
    table.loc["NPV over the horizon"] = npv
    return table


def render(ctx: Context) -> None:
    r, cur = ctx.cases, ctx.cur
    cc = chips(ctx)
    components.hero(
        "Chamchuri 5: what do solar and smart rules save?",
        "Hourly 2019 load of the Chulalongkorn research office tower, priced on the MEA Type 3.2 TOU tariff. "
        "Four cases, from the roof as it is today to a what-if plant on other land with net metering.",
        list(cc.values()),
    )

    components.section("The four cases at a glance")
    pv_saving, total_saving = r.pv_saving_thb, r.total_saving_thb
    cols = st.columns(4)
    with cols[0]:
        components.case_card(
            cc[1], "Today",
            "The building as we receive it, with the existing 20 kWp array on half of the roof.",
            cur.money(r.case1.bill.total_thb), "annual electricity bill",
        )
    with cols[1]:
        components.case_card(
            cc[2], "New solar",
            f"A new {PLANT.new_kwp:g} kWp array on the free half of the roof, next to the old one.",
            f"-{cur.money(pv_saving)}/yr", f"{years(r.pv_economics.payback_years)} payback",
        )
    with cols[2]:
        components.case_card(
            cc[3], "Solar + rules",
            "Case 2 plus two off-hours rules: dim the lighting and set back the air conditioning.",
            f"-{cur.money(total_saving)}/yr", f"{pct(total_saving / r.case1.bill.total_thb)} of today's bill",
        )
    with cols[3]:
        if case4.plant_available():
            c4 = ctx.case4
            components.case_card(
                cc[4], "What-if: plant on other land",
                f"Suppose a {c4.spec.capacity_kwp:g} kWp plant on open land fed the grid and its energy were credited on the bill at {c4.credit:.2f} THB/kWh.",
                f"-{cur.money(c4.saving_vs_case1_thb)}/yr",
                f"{years(c4.vs_case3.payback_years)} payback of the plant (hypothetical)",
            )
        else:
            components.case_card(
                cc[4], "What-if: plant on other land",
                "A larger plant off the roof, credited against the bill (virtual net metering). Waiting for the plant data.",
                "In preparation", "Sizing snapshot on its page",
            )

    components.section("Where the savings come from", "Annual saving against Case 1, in " + cur.unit + ".")
    left, right = st.columns([1.1, 1])
    with left:
        fig = charts.waterfall(
            ["New PV array", "Off-hours rules", "Total saving"],
            [pv_saving, r.dsm_saving_thb, total_saving], cur,
        )
        components.show(fig, "ov_waterfall")
    with right:
        names = ["No PV", "Case 1", "Case 2", "Case 3"]
        bills = [r.no_pv.bill.total_thb, r.case1.bill.total_thb, r.case2.bill.total_thb, r.case3.bill.total_thb]
        colors = [theme.MUTED, theme.CASE_COLOR[1], theme.CASE_COLOR[2], theme.CASE_COLOR[3]]
        if case4.plant_available():
            names.append("Case 4")
            bills.append(ctx.case4.scenario.bill.total_thb)
            colors.append(theme.CASE_COLOR[4])
        components.show(charts.bill_by_case(names, bills, colors, cur), "ov_bills")

    components.section("Side by side")
    components.table(summary_table(ctx))

    components.section("What to take away")
    rules_vs_pv = r.dsm_saving_thb / pv_saving if pv_saving > 0 else float("nan")
    components.callout(
        f"**The rules save {pct(rules_vs_pv, 0)} as much as the new array** ({cur.money(r.dsm_saving_thb)} against "
        f"{cur.money(pv_saving)} a year) and need no purchase. Their size rests on two assumed cut percentages "
        "(set in the sidebar), so treat it as a target to prove with a pilot.", "good",
    )
    components.callout(
        f"**Solar is too small to export.** {pct(r.case2.self_consumption, 3)} of the new plant's energy is used inside "
        f"the building ({r.case2.export_kwh:,.1f} kWh exported in a year), so net metering has no value at this size. "
        "Case 4 is about what changes when the plant grows.", "info",
    )
    if case4.plant_available():
        c4 = ctx.case4
        components.callout(
            f"**What if the roof were not the limit?** Case 4 assumes a {c4.spec.capacity_kwp:g} kWp plant on other land, all of "
            f"its {mwh(c4.plant_kwh)} sent to the grid and credited on the bill. At {c4.credit:.2f} THB/kWh that is "
            f"{cur.money(c4.export_revenue_thb)} a year and a payback of {years(c4.vs_case3.payback_years).lower()}; the credit price "
            f"decides the result. The modules need about {c4.module_area_needed_m2:,.0f} m², more than the free roof half, and "
            "the site, the legal basis of net metering and the price are assumptions.", "info",
        )
    components.callout(
        f"**Data quality.** {pct(ctx.data.filled_share)} of the building's 2019 energy was gap-filled by the dataset "
        "preparer; the existing 20 kWp array is estimated from a satellite image (±25%) and no PV output was metered; "
        "equipment prices are placeholders until quotes arrive. See the Methodology page.", "warn",
    )

    components.section("The site")
    a, b = st.columns(2)
    with a:
        components.photo_figure("building_photo.jpg", "Chamchuri 5, ground floor entrance.")
    with b:
        components.photo_figure(
            "roof_annotated.jpg",
            "Roof of Chamchuri 5. The existing 20 kWp array occupies one half; the new array goes on the free half "
            "(592 m² measured, about 350 m² of modules).",
        )
