"""Methodology: data lineage, assumptions, tariff and a live reconciliation with the Excel model."""

from __future__ import annotations

import pandas as pd

from .. import components
from ..config import DSM, FINANCE, GRID, PLANT, TARIFF
from ..context import Context, get_cases
from ..fmt import pct
from ..model import Settings


def _assumptions() -> pd.DataFrame:
    rows = [
        ("Hourly building load, 2019", "8,760 h, 7 floors, 3 end uses", "MEASURED", "CU-BEMS dataset; part of it gap-filled by the preparer (see Overview)."),
        ("Existing PV array", f"{PLANT.existing_kwp:g} kWp", "ESTIMATED", "From a satellite image, ±25%. No metered output exists."),
        ("New PV array", f"{PLANT.new_kwp:g} kWp (135 × 550 W)", "DESIGN", "Sheet_final sizing: about 350 m² of modules on the free half of the roof."),
        ("PV hourly profile", "Typical day for each month", "MODELLED", "Sheet_final profiles; no day-to-day weather variation."),
        ("Tariff", f"MEA Type 3.2 TOU: {TARIFF.on_peak_base:g} / {TARIFF.off_peak_base:g} THB/kWh, demand {TARIFF.demand_charge:g} THB/kW", "SUPPLIED", "Plus Ft 0.1623 THB/kWh and 7% VAT; the building's true category is unconfirmed."),
        ("On-peak window", f"Mon-Fri {TARIFF.on_peak_start:02d}:00-{TARIFF.on_peak_end:02d}:00", "SUPPLIED", "Public holidays are treated as normal workdays."),
        ("Export price", f"{TARIFF.export_price:g} THB/kWh", "SUPPLIED", "Thai buy-back; irrelevant at this plant size."),
        ("PV installed price", f"{FINANCE.pv_cost_per_kwp:,.0f} THB/kWp", "ASSUMED", "Rooftop C&I placeholder until quotes arrive; editable in the sidebar."),
        ("PV O&M", f"{FINANCE.pv_om_per_kwp:g} THB/kWp/year", "ASSUMED", "About 1% of the capital cost."),
        ("Finance", f"{pct(FINANCE.discount_rate, 0)} discount, {pct(FINANCE.escalation, 0)} escalation, {pct(FINANCE.degradation)} degradation, {FINANCE.horizon_years} years", "ASSUMED", "Same conventions as the Excel model."),
        ("Lighting cut, off-hours", f"{pct(DSM.light_cut, 0)} (default)", "ASSUMED", "Scenario value to be proven by a pilot."),
        ("AC cut, off-hours", f"{pct(DSM.ac_cut, 0)} (default)", "ASSUMED", "Scenario value to be proven by a pilot."),
        ("Off-hours", f"Weekends; workdays before {DSM.work_start_hour:02d}:00 and from {DSM.work_end_hour:02d}:00", "ASSUMED", "Hours are adjustable in the sidebar. Optionally also low-use workdays (below 65% of the median workday)."),
        ("Case 4 plant", "550 kWp, 1,000 × 550 W, tilt 15°, south", "SUPPLIED", "Project team sheet (PVGIS-based, losses 14%): typical day for each month, same shape as the existing array."),
        ("Case 4 site", "Open land elsewhere (hypothetical)", "ASSUMED", "The roof has no room. All of the plant's output is sent to the grid and credited on the building's bill; the roof arrays are unchanged."),
        ("Case 4 credit", f"{TARIFF.export_price:g} THB/kWh (default)", "ASSUMED", "Thai buy-back. The retail TOU price is shown as an upper bound; the legal basis and price of virtual net metering are unconfirmed."),
        ("Transformer limit", f"{GRID.transformer_kva:,.0f} kVA × {GRID.power_factor:g}", "ASSUMED", "Used only to flag exports that would exceed what the transformer can carry."),
    ]
    return pd.DataFrame(rows, columns=["Item", "Value", "Status", "Note"]).set_index("Item")


def _reconciliation(ctx: Context) -> pd.DataFrame:
    """Dashboard against the Excel model for Cases 1 and 2, always with the default settings."""
    ref = ctx.reference
    res = get_cases(ctx.data, Settings())
    eco = res.pv_economics
    checks = [
        ("Annual bill, Case 1 (Excel S0), THB", ref["S0"]["bill_thb"], res.case1.bill.total_thb),
        ("Annual bill, Case 2 (Excel S1), THB", ref["S1"]["bill_thb"], res.case2.bill.total_thb),
        ("Annual bill with no PV, THB", ref["annual_bill_no_pv_thb"], res.no_pv.bill.total_thb),
        ("PV production, Case 2, kWh", ref["S1"]["pv_kwh"], res.case2.pv_kwh),
        ("Grid import, Case 2, kWh", ref["S1"]["grid_kwh"], res.case2.grid_kwh),
        ("Billed on-peak demand, Case 2, kW", ref["S1"]["peak_onpeak_kw"], res.case2.peak_onpeak_kw),
        ("Saving of the new array, THB/year", ref["S1"]["saving_thb"], res.pv_saving_thb),
        ("Simple payback, years", ref["S1"]["payback_y"], eco.payback_years),
        ("NPV, THB", ref["S1"]["npv_thb"], eco.npv_thb),
        ("IRR", ref["S1"]["irr"], eco.irr),
    ]
    rows = []
    for name, excel, python in checks:
        diff = python - excel
        rows.append((name, f"{excel:,.3f}", f"{python:,.3f}", f"{diff:+,.3f}", "match" if abs(diff) <= max(1.0, 1e-6 * abs(excel)) else "check"))
    return pd.DataFrame(rows, columns=["Quantity", "Excel model", "This dashboard", "Difference", "Result"]).set_index("Quantity")


def render(ctx: Context) -> None:
    components.page_header(
        components.CaseChip("Methodology", "#7D8CA5"),
        "How the numbers are made",
        "What is measured, what is assumed, and proof that the dashboard reproduces the Excel strategy model.",
    )

    components.section("Method in five lines")
    components.callout(
        "**1.** Each hour, PV serves the building first; any surplus is exported. **2.** The grid import is priced on the MEA "
        "Type 3.2 TOU tariff: energy by on-peak and off-peak hour, a monthly demand charge on the highest on-peak hour, a service charge, "
        "Ft and 7% VAT. **3.** Savings are the difference between the bills of two cases. **4.** Cash flows grow with the tariff and "
        "shrink with PV degradation; NPV, IRR and simple payback follow the Excel model's conventions. **5.** The two rules change the "
        "load itself (lighting and air conditioning in off-hours), then the same PV and tariff are applied.", "info",
    )

    components.section("Assumptions and their status", "MEASURED and SUPPLIED come from project files; ESTIMATED, MODELLED and ASSUMED need confirmation.")
    components.table(_assumptions())

    components.section("Reconciliation with the Excel model", "Cases 1 and 2 are recomputed here from the hourly data with the default settings.")
    table = _reconciliation(ctx)
    components.table(table)
    if (table["Result"] == "match").all():
        components.callout("All quantities match the Excel model.", "good")
    else:
        components.callout("Some quantities differ from the Excel model: see the rows marked 'check'.", "warn")

    components.section("Open points")
    components.callout(
        "**1.** Real bill, tariff category, Ft and 15-minute demand. **2.** Metered output of the existing 20 kWp array. "
        "**3.** Orientation of the new array (Sheet_final used azimuth 0). **4.** Quotes for PV and installation. "
        "**5.** Pilot results to replace the 40% and 25% cut assumptions. **6.** Case 4 is a what-if: a real site "
        "(the plant needs far more space than the free roof half), its cost, and the legal basis and price of net metering.", "warn",
    )

    components.section("Data source")
    components.callout(
        "Load data: Pipattanasomporn et al., CU-BEMS, a smart building electricity consumption and indoor environmental "
        "sensor dataset, Scientific Data 7:241 (2020), CC BY 4.0. Solar and economic model: Chamchuri5_Solar_Strategy_v5.xlsx.", "info",
    )
