"""Chamchuri 5 solar and demand-side savings dashboard.

Run from this folder:   streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Chamchuri 5 · Solar and savings", page_icon="☀️", layout="wide", initial_sidebar_state="expanded")

from dashboard import components, data as data_mod  # noqa: E402  (after set_page_config)
from dashboard.config import DEFAULT_THB_PER_USD, DSM, FINANCE, TARIFF  # noqa: E402
from dashboard.context import Context, get_cases, get_data  # noqa: E402
from dashboard.engine import NEW_ARRAY_AS_SUPPLIED, NEW_ARRAY_SOUTH  # noqa: E402
from dashboard.fmt import THB, USD, Currency  # noqa: E402
from dashboard.model import Settings  # noqa: E402
from dashboard.views import case1, case2, case3, case4, methodology, overview  # noqa: E402

ORIENTATION = {"As supplied (Sheet_final)": NEW_ARRAY_AS_SUPPLIED, "South-facing (like the old array)": NEW_ARRAY_SOUTH}


def sidebar() -> tuple[Settings, Currency]:
    """Draw the controls shared by every page and return their values."""
    with st.sidebar:
        st.markdown('<div class="brand">Chamchuri 5<small>Solar and savings · 2019 hourly data</small></div>', unsafe_allow_html=True)
        st.divider()
        code = st.radio("Currency", [THB, USD], horizontal=True, key="currency")
        rate = st.number_input("THB per USD", min_value=20.0, max_value=60.0, value=DEFAULT_THB_PER_USD, step=0.05,
                               key="fx", help="Editable. Default is the quote of 2026-10-27.")
        with st.expander("Solar assumptions"):
            label = st.radio("Orientation of the new array", list(ORIENTATION), key="orientation",
                             help="Sheet_final may have entered the new array facing north. Compare both.")
            price = st.slider("PV installed price (THB/kWp)", 15_000, 40_000, int(FINANCE.pv_cost_per_kwp), 500, key="pv_price",
                              help="Placeholder until quotes arrive.")
        with st.expander("Off-hours rules"):
            light = st.slider("Lighting cut", 0, 80, 40, 5, format="%d%%", key="light_cut")
            ac = st.slider("Air-conditioning cut", 0, 60, 25, 5, format="%d%%", key="ac_cut")
            start, end = st.slider("Working hours on workdays", 0, 24, (DSM.work_start_hour, DSM.work_end_hour), 1,
                                   format="%d h", key="work_hours",
                                   help="The rules apply outside this window on workdays, and all day on weekends.")
            if start >= end:  # an empty window would be rejected by the engine; fall back to the defaults
                st.warning("Working hours need a start before the end; using the defaults.")
                start, end = DSM.work_start_hour, DSM.work_end_hour
            low_use = st.checkbox("Apply also on low-use workdays (probable holidays)", value=False, key="low_use")
            dsm_cost = st.number_input("Cost to implement the rules (THB)", min_value=0, value=0, step=10_000, key="dsm_cost",
                                       help="Zero until the team estimates controls and commissioning.")
        with st.expander("Case 4 what-if (off-site plant)"):
            credit = st.slider("Credit for the plant's energy (THB/kWh)", 0.0, 5.0, float(TARIFF.export_price), 0.05,
                               key="c4_credit", help="2.20 is the Thai buy-back; about 4.7 is the retail on-peak price (full net metering).")
        st.caption("Every number on the pages follows these controls.")
    settings = Settings(
        new_array=ORIENTATION[label], light_cut=light / 100, ac_cut=ac / 100, low_use_as_holiday=low_use,
        pv_cost_per_kwp=float(price), dsm_cost_thb=float(dsm_cost),
        work_start_hour=int(start), work_end_hour=int(end),
        c4_credit=float(credit),
    )
    return settings, Currency(code, float(rate))


def main() -> None:
    components.inject_theme()
    try:
        data = get_data()
        sizing_pv, sizing_battery = data_mod.load_sizing()
        reference = data_mod.load_reference()
    except (OSError, ValueError) as exc:
        st.error(f"The data files could not be loaded: {exc}")
        st.stop()

    settings, cur = sidebar()
    ctx = Context(data, settings, cur, get_cases(data, settings), sizing_pv, sizing_battery, reference)

    def page(module):
        def run() -> None:
            module.render(ctx)
        run.__name__ = module.__name__.rsplit(".", 1)[-1]
        return run

    navigation = st.navigation([
        st.Page(page(overview), title="Overview", icon="🏠", url_path="overview", default=True),
        st.Page(page(case1), title="Case 1 · Today", icon="🏢", url_path="case-1-today"),
        st.Page(page(case2), title="Case 2 · New solar", icon="☀️", url_path="case-2-new-solar"),
        st.Page(page(case3), title="Case 3 · Solar + rules", icon="💡", url_path="case-3-solar-and-rules"),
        st.Page(page(case4), title="Case 4 · What-if", icon="🔭", url_path="case-4-what-if"),
        st.Page(page(methodology), title="Methodology", icon="📐", url_path="methodology"),
    ])
    navigation.run()


main()
