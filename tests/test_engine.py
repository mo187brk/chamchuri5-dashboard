"""Reconcile the Python engine with the Excel strategy model and check its invariants.

Run from the project root:  python -m pytest -q     (or: python -m unittest discover -s tests)
"""

from __future__ import annotations

import unittest

import numpy as np

from dashboard import data as data_mod
from dashboard.config import FINANCE, PLANT
from dashboard.engine import (
    NEW_ARRAY_SOUTH,
    DsmRules,
    apply_rules,
    compute_bill,
    off_hours_mask,
    project_economics,
    simulate,
)
from dashboard.model import Settings, run_cases

DATA = data_mod.load_hourly()
REF = data_mod.load_reference()
CASES = run_cases(DATA)


class ExcelReconciliation(unittest.TestCase):
    """The numbers in the Excel model are the ground truth for Cases 1 and 2."""

    def test_load_energy_and_peak(self):
        self.assertAlmostEqual(DATA.load_kw.sum() / 1e3, 2183.946, places=2)
        self.assertAlmostEqual(DATA.load_kw.max(), 843.852, places=2)

    def test_category_shares(self):
        ac = DATA.frame["ac_kw"].sum() / 1e3
        self.assertAlmostEqual(ac, 1203.15, places=1)
        self.assertAlmostEqual(100 * ac / (DATA.load_kw.sum() / 1e3), 55.09, places=1)

    def test_case1_bill_matches_excel_s0(self):
        self.assertAlmostEqual(CASES.case1.bill.total_thb, REF["S0"]["bill_thb"], delta=1.0)
        self.assertAlmostEqual(CASES.case1.pv_kwh, REF["S0"]["pv_kwh"], delta=0.5)
        self.assertAlmostEqual(CASES.case1.peak_onpeak_kw, REF["S0"]["peak_onpeak_kw"], places=3)

    def test_no_pv_bill_matches_excel(self):
        self.assertAlmostEqual(CASES.no_pv.bill.total_thb, REF["annual_bill_no_pv_thb"], delta=1.0)

    def test_case2_bill_matches_excel_s1(self):
        self.assertAlmostEqual(CASES.case2.bill.total_thb, REF["S1"]["bill_thb"], delta=1.0)
        self.assertAlmostEqual(CASES.case2.pv_kwh, REF["S1"]["pv_kwh"], delta=0.5)
        self.assertAlmostEqual(CASES.case2.export_kwh, REF["S1"]["export_kwh"], places=2)
        self.assertAlmostEqual(CASES.case2.grid_kwh, REF["S1"]["grid_kwh"], delta=0.5)
        self.assertAlmostEqual(CASES.case2.peak_onpeak_kw, REF["S1"]["peak_onpeak_kw"], places=3)

    def test_case2_economics_match_excel(self):
        eco = CASES.pv_economics
        self.assertAlmostEqual(CASES.pv_saving_thb, REF["S1"]["saving_thb"], delta=1.0)
        self.assertAlmostEqual(eco.capex_thb, REF["S1"]["capex_thb"], places=2)
        self.assertAlmostEqual(eco.payback_years, REF["S1"]["payback_y"], places=3)
        self.assertAlmostEqual(eco.npv_thb, REF["S1"]["npv_thb"], delta=2.0)
        self.assertAlmostEqual(eco.irr, REF["S1"]["irr"], places=4)

    def test_cash_flow_first_years_match_excel(self):
        expected = [-1930500, 417237.181, 423355.559, 429563.133, 435861.19]
        np.testing.assert_allclose(CASES.pv_economics.cashflows_thb[:5], expected, atol=0.01)

    def test_south_facing_alternative_matches_excel_change_log(self):
        south = run_cases(DATA, Settings(new_array=NEW_ARRAY_SOUTH))
        alt = REF["alt_south_new_array"]
        self.assertAlmostEqual(south.case2.pv_kwh, alt["pv_kwh"], delta=5)
        self.assertAlmostEqual(south.pv_saving_thb, alt["saving_thb"], delta=5)
        self.assertAlmostEqual(south.pv_economics.payback_years, alt["payback_y"], places=2)
        self.assertAlmostEqual(south.pv_economics.npv_thb, alt["npv_thb"], delta=5)


class EngineInvariants(unittest.TestCase):
    def test_energy_balance_every_hour(self):
        for case in (CASES.case1, CASES.case2, CASES.case3):
            np.testing.assert_allclose(case.used_kw + case.grid_kw, case.load_kw, atol=1e-9)
            np.testing.assert_allclose(case.used_kw + case.export_kw, case.pv_kw, atol=1e-9)
            self.assertTrue((case.grid_kw >= 0).all() and (case.export_kw >= 0).all())

    def test_bill_components_add_up(self):
        monthly = CASES.case2.bill.monthly
        parts = monthly[["energy_on_thb", "energy_off_thb", "demand_thb", "service_thb", "export_credit_thb"]].sum()
        self.assertAlmostEqual(parts.sum(), monthly["total_thb"].sum(), places=6)
        self.assertEqual(len(monthly), 12)

    def test_pv_is_zero_at_night(self):
        night = (DATA.calendar.hour < 5) | (DATA.calendar.hour > 19)
        self.assertEqual(CASES.case2.pv_kw[night].max(), 0.0)

    def test_savings_are_ordered(self):
        self.assertLess(CASES.case2.bill.total_thb, CASES.case1.bill.total_thb)
        self.assertLess(CASES.case3.bill.total_thb, CASES.case2.bill.total_thb)
        self.assertLess(CASES.case1.bill.total_thb, CASES.no_pv.bill.total_thb)

    def test_bill_rejects_bad_input(self):
        cal = DATA.calendar
        with self.assertRaises(ValueError):
            compute_bill(np.zeros(10), np.zeros(10), cal)
        with self.assertRaises(ValueError):
            compute_bill(-np.ones(cal.n_hours), np.zeros(cal.n_hours), cal)

    def test_zero_pv_scenario_is_pure_load(self):
        zero = simulate(DATA.load_kw, np.zeros(DATA.calendar.n_hours), DATA.calendar)
        np.testing.assert_allclose(zero.grid_kw, DATA.load_kw)
        self.assertEqual(zero.export_kwh, 0.0)


class DemandSideRules(unittest.TestCase):
    def test_rules_only_touch_off_hours_and_never_plug_load(self):
        dsm = CASES.dsm
        self.assertEqual(dsm.saved_kw[~dsm.off_mask].max(), 0.0)
        frame = DATA.frame
        expected = 0.40 * frame["light_kw"].to_numpy()[dsm.off_mask].sum() + 0.25 * frame["ac_kw"].to_numpy()[dsm.off_mask].sum()
        self.assertAlmostEqual(dsm.saved_kw.sum(), expected, places=6)

    def test_zero_cut_changes_nothing(self):
        rules = DsmRules(light_cut=0.0, ac_cut=0.0)
        cal = DATA.calendar
        res = apply_rules(DATA.load_kw, DATA.frame["ac_kw"].to_numpy(), DATA.frame["light_kw"].to_numpy(),
                          off_hours_mask(cal, rules), rules)
        np.testing.assert_allclose(res.load_kw, DATA.load_kw)

    def test_off_hours_definition(self):
        cal = DATA.calendar
        mask = off_hours_mask(cal, DsmRules())
        self.assertTrue(mask[cal.weekend].all())
        weekday_noon = (~cal.weekend) & (cal.hour == 12)
        self.assertFalse(mask[weekday_noon].any())
        weekday_night = (~cal.weekend) & ((cal.hour >= 20) | (cal.hour < 6))
        self.assertTrue(mask[weekday_night].all())

    def test_low_use_days_are_workdays(self):
        low = CASES.low_use
        self.assertFalse((low & CASES.dsm.off_mask & DATA.calendar.weekend).any())
        self.assertEqual(low.sum() % 24, 0)
        self.assertGreater(low.sum() // 24, 0)

    def test_holiday_option_increases_savings(self):
        with_holidays = run_cases(DATA, Settings(low_use_as_holiday=True))
        self.assertGreater(with_holidays.dsm_saving_thb, CASES.dsm_saving_thb)

    def test_rules_do_not_reduce_demand_charge_much(self):
        # Rules act off-hours, so the billed on-peak demand must be (almost) unchanged.
        self.assertAlmostEqual(CASES.case3.peak_onpeak_kw, CASES.case2.peak_onpeak_kw, delta=1.0)

    def test_shorter_working_day_widens_the_rules_and_saves_more(self):
        shorter = run_cases(DATA, Settings(work_start_hour=8, work_end_hour=18))
        self.assertGreater(shorter.dsm_saving_thb, CASES.dsm_saving_thb)
        self.assertAlmostEqual(shorter.case3.peak_onpeak_kw, shorter.case2.peak_onpeak_kw, delta=25.0)

    def test_settings_survive_the_cache_key_round_trip(self):
        from dataclasses import astuple

        custom = Settings(new_array=NEW_ARRAY_SOUTH, light_cut=0.3, work_start_hour=7, work_end_hour=19, dsm_cost_thb=5.0)
        self.assertEqual(Settings(*astuple(custom)), custom)

    def test_invalid_rules_are_rejected(self):
        with self.assertRaises(ValueError):
            DsmRules(light_cut=1.5)
        with self.assertRaises(ValueError):
            DsmRules(work_start_hour=20, work_end_hour=6)


class Economics(unittest.TestCase):
    def test_no_capex_has_zero_payback_and_no_irr(self):
        eco = project_economics(0.0, 0.0, 100_000.0, 0.0)
        self.assertEqual(eco.payback_years, 0.0)
        self.assertIsNone(eco.irr)
        self.assertGreater(eco.npv_thb, 0)

    def test_negative_net_benefit_has_no_payback(self):
        eco = project_economics(1_000_000.0, 10_000.0, 0.0, 50_000.0)
        self.assertIsNone(eco.payback_years)
        self.assertLess(eco.npv_thb, 0)

    def test_irr_makes_npv_zero(self):
        eco = CASES.pv_economics
        years = np.arange(len(eco.cashflows_thb))
        residual = np.sum(eco.cashflows_thb / (1 + eco.irr) ** years)
        self.assertAlmostEqual(residual, 0.0, delta=1e-3)

    def test_combined_project_adds_up(self):
        total = CASES.total_economics
        self.assertAlmostEqual(total.saving_year1_thb, CASES.pv_saving_thb + CASES.dsm_saving_thb, places=4)
        self.assertAlmostEqual(CASES.total_saving_thb, CASES.pv_saving_thb + CASES.dsm_saving_thb, places=4)
        self.assertAlmostEqual(total.capex_thb, PLANT.new_kwp * FINANCE.pv_cost_per_kwp, places=4)

    def test_dsm_cost_enters_combined_capex(self):
        costly = run_cases(DATA, Settings(dsm_cost_thb=250_000.0))
        self.assertAlmostEqual(costly.total_economics.capex_thb, CASES.total_economics.capex_thb + 250_000.0, places=4)
        self.assertGreater(costly.dsm_economics.payback_years, 0.0)


class DataValidation(unittest.TestCase):
    def test_validation_catches_problems(self):
        good = DATA.frame.reset_index()
        data_mod.validate_hourly(good)
        with self.assertRaises(ValueError):
            data_mod.validate_hourly(good.iloc[:-1])
        broken = good.copy()
        broken.loc[5, "ac_kw"] += 10.0
        with self.assertRaises(ValueError):
            data_mod.validate_hourly(broken)
        nan = good.copy()
        nan.loc[3, "load_kw"] = np.nan
        with self.assertRaises(ValueError):
            data_mod.validate_hourly(nan)

    def test_gap_filled_share_is_about_7_6_percent(self):
        self.assertAlmostEqual(100 * DATA.filled_share, 7.6, delta=0.1)


if __name__ == "__main__":
    unittest.main()
