"""Case 3: Case 2 plus the two off-hours rules (lighting and air-conditioning)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import analytics, charts, components, theme
from ..components import CaseChip, Kpi
from ..context import Context
from ..fmt import kw, mwh, pct, years


def render(ctx: Context) -> None:
    d, r, cur, s = ctx.data, ctx.cases, ctx.cur, ctx.settings
    cal, frame = d.calendar, d.frame
    c1, c2, c3, dsm = r.case1, r.case2, r.case3, r.dsm
    tone = theme.CASE_COLOR[3]
    rules = s.rules
    saved_kwh = float(dsm.saved_kw.sum())
    dsm_saving = r.dsm_saving_thb
    total_saving = r.total_saving_thb
    total_eco, dsm_eco = r.total_economics, r.dsm_economics

    components.page_header(
        CaseChip("Case 3 · Solar + rules", tone),
        "Case 3: solar plus two off-hours rules",
        "Rule 1 dims the lighting and rule 2 sets back the air conditioning whenever the building is not in use: nights, "
        "weekends and, optionally, low-use workdays.",
    )

    holiday_text = " and low-use workdays (probable holidays)" if s.low_use_as_holiday else ""
    components.callout(
        f"**Rules applied.** Off-hours are every hour of weekends, plus workdays before {rules.work_start_hour:02d}:00 and from "
        f"{rules.work_end_hour:02d}:00{holiday_text}. In those hours: **(1) lighting is cut by {pct(s.light_cut, 0)}** and "
        f"**(2) air-conditioning load is cut by {pct(s.ac_cut, 0)}**. Plug loads are untouched. The two percentages are "
        "scenario assumptions, not measurements: change them in the sidebar.", "info",
    )

    components.kpi_row([
        Kpi("Energy saved by the rules", mwh(saved_kwh), f"{pct(saved_kwh / c2.load_kwh)} of building energy", tone),
        Kpi("Extra saving from the rules", cur.money(dsm_saving), f"{cur.secondary(dsm_saving)} per year on top of Case 2", tone,
            delta=f"{pct(dsm_saving / c1.bill.total_thb)} of today's bill"),
        Kpi("Total saving vs Case 1", cur.money(total_saving), f"new PV {cur.money(r.pv_saving_thb)} + rules {cur.money(dsm_saving)}", tone,
            delta=f"{pct(total_saving / c1.bill.total_thb)} of today's bill"),
        Kpi("Annual electricity bill", cur.money(c3.bill.total_thb), f"against {cur.money(c1.bill.total_thb)} today", tone),
        Kpi("Billed on-peak demand", kw(c3.peak_onpeak_kw), f"Case 2: {kw(c2.peak_onpeak_kw)} · Case 1: {kw(c1.peak_onpeak_kw)}", tone),
        Kpi("Peak shaving from the rules", pct((c2.peak_onpeak_kw - c3.peak_onpeak_kw) / c2.peak_onpeak_kw),
            "rules act off-hours, when the building is not at its peak", tone),
        Kpi("Payback of PV + rules", years(total_eco.payback_years), f"rules cost {cur.money(s.dsm_cost_thb)} (set in the sidebar)", tone),
        Kpi("NPV of PV + rules", cur.money(total_eco.npv_thb),
            f"IRR {pct(total_eco.irr)}" if total_eco.irr is not None else "IRR not defined", tone),
    ])

    tabs = st.tabs(["Saving build-up", "Day types", "Load by end use", "What if?"])

    with tabs[0]:
        a, b = st.columns(2)
        with a:
            st.markdown("**Annual saving against Case 1**")
            components.show(charts.waterfall(["New PV array", "Off-hours rules", "Total saving"],
                                             [r.pv_saving_thb, dsm_saving, total_saving], cur), "c3_waterfall")
        with b:
            st.markdown("**Energy saved by the rules each month**")
            table = analytics.monthly_table({"Air conditioning": dsm.saved_ac_kw, "Lighting": dsm.saved_light_kw}, cal)
            components.show(charts.stacked_months(table, theme.SAVING_USE, "Energy saved (MWh)", "MWh"), "c3_saved")
        components.data_table(table.round(2), "c3_saved", "case3_energy_saved_by_rules_mwh.csv")

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
                    "Base load (Case 1)": (prof(c1.load_kw, cal, mask), theme.LOAD, "solid"),
                    "Load after rules": (prof(c3.load_kw, cal, mask), theme.SAVE, "dash"),
                    "Grid after PV + rules": (prof(c3.grid_kw, cal, mask), theme.GRID, "solid"),
                    "PV (whole plant)": (prof(c3.pv_kw, cal, mask), theme.PV_NEW, "solid"),
                },
            ))
        components.show(charts.day_type_panels(panels), "c3_daytypes")
        components.callout(
            "The rules bite on weekends (dashed green far below the grey line) and at night, and leave the busy workday "
            "hours alone. Low-use workdays are probable holidays: switch them on in the sidebar to apply the rules to them too.", "info",
        )

    with tabs[2]:
        before = analytics.category_energy(frame)
        after = before.copy()
        after["Air conditioning"] -= dsm.saved_ac_kw.sum() / 1e3
        after["Lighting"] -= dsm.saved_light_kw.sum() / 1e3
        table = pd.DataFrame({"Before rules": before, "After rules": after}).T
        components.show(charts.stacked_months(table, theme.END_USE, "Annual energy (MWh)", "MWh"), "c3_enduse")
        components.data_table(table.round(1), "c3_enduse", "case3_load_by_end_use_mwh.csv")

    with tabs[3]:
        st.markdown("**Extra annual saving (on top of Case 2) for other cut percentages**")
        table = analytics.sweep_savings(
            d.load_kw, frame["ac_kw"].to_numpy(), frame["light_kw"].to_numpy(), c2.pv_kw, cal,
            c2.bill.total_thb, [0.2, 0.4, 0.6], [0.1, 0.25, 0.4], r.low_use, s.low_use_as_holiday,
        )
        components.show(charts.saving_grid(table, cur), "c3_whatif")
        st.caption("Each cell re-runs the full year with that pair of cuts; the sidebar sliders set the headline numbers above.")

    components.note_panels(
        applied=[
            f"Rule 1: lighting **-{pct(s.light_cut, 0)}** in off-hours. Rule 2: air conditioning **-{pct(s.ac_cut, 0)}** in off-hours.",
            f"Off-hours: weekends, and workdays before {rules.work_start_hour:02d}:00 or from {rules.work_end_hour:02d}:00"
            + (", plus low-use workdays." if s.low_use_as_holiday else "."),
            "Solar as in Case 2 (existing + new array). Same tariff.",
        ],
        results=[
            f"The rules cut **{mwh(saved_kwh)}** a year and save **{cur.money(dsm_saving)}**, about {pct(dsm_saving / r.pv_saving_thb, 0)} of what the new array saves.",
            f"With solar the bill falls by **{cur.money(total_saving)}** ({pct(total_saving / c1.bill.total_thb)}).",
            f"Rules cost {cur.money(s.dsm_cost_thb)} here, so their payback is {years(dsm_eco.payback_years).lower()}.",
        ],
        notes=[
            "The cut percentages are assumptions to be proven by a pilot on one floor; the energy saved scales with them.",
            "Because the rules work off-hours they hardly lower the billed peak demand; the peak reduction comes from solar.",
            "Comfort and safety limits (security lighting, server rooms, early-start classes) are not modelled.",
        ],
    )
