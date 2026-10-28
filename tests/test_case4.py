"""Case 4 (what-if): plant data, the optional hourly file, the off-site simulation and the value of the credit."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from dashboard import case4, data as data_mod
from dashboard.engine import simulate
from dashboard.model import Settings, run_cases

DATA = data_mod.load_hourly()
CASES = run_cases(DATA)
SPEC = case4.load_plant_spec()
SETTINGS = Settings()


def _frame(pv: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"datetime": DATA.calendar.index, "pv_expanded_kw": pv})


class ExpandedFileValidation(unittest.TestCase):
    """The optional hourly file that can replace the monthly profile."""

    def setUp(self):
        self.pv = CASES.case3.pv_kw * 3.0

    def test_valid_file_passes(self):
        case4.validate_expanded(_frame(self.pv), DATA)

    def test_missing_column(self):
        with self.assertRaisesRegex(ValueError, "missing columns"):
            case4.validate_expanded(_frame(self.pv).drop(columns="pv_expanded_kw"), DATA)

    def test_wrong_length(self):
        with self.assertRaisesRegex(ValueError, "rows"):
            case4.validate_expanded(_frame(self.pv).iloc[:-1], DATA)

    def test_misaligned_timestamps(self):
        frame = _frame(self.pv)
        frame["datetime"] = frame["datetime"] + pd.Timedelta(hours=1)
        with self.assertRaisesRegex(ValueError, "Timestamps"):
            case4.validate_expanded(frame, DATA)

    def test_negative_and_missing_values(self):
        bad = self.pv.copy(); bad[10] = -1.0
        with self.assertRaisesRegex(ValueError, "negative"):
            case4.validate_expanded(_frame(bad), DATA)
        bad = self.pv.copy(); bad[10] = np.nan
        with self.assertRaisesRegex(ValueError, "missing or non-numeric"):
            case4.validate_expanded(_frame(bad), DATA)

    def test_absent_file_means_no_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(case4.load_expanded_plant(DATA, Path(tmp) / "nope.csv"))

    def test_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case4_expanded.csv"
            _frame(self.pv).to_csv(path, index=False)
            loaded = case4.load_expanded_plant(DATA, path)
        np.testing.assert_allclose(loaded, self.pv, atol=1e-9)


class PlantData(unittest.TestCase):
    """The plant sheet supplied by the team is reproduced exactly."""

    def test_system_data(self):
        self.assertEqual(SPEC.capacity_kwp, 550.0)
        self.assertEqual(SPEC.modules, 1000)
        self.assertAlmostEqual(SPEC.module_kw, 0.55)
        self.assertEqual(SPEC.module_area_total_m2, 2600.0)

    def test_profile_columns_add_up_to_the_sheet(self):
        daily_wh = case4.load_profile().sum(axis=0)
        self.assertEqual(daily_wh.tolist(), [4175, 4327, 4349, 4231, 3701, 3488, 3240, 3466, 3432, 3460, 3860, 4188])

    def test_annual_energy_matches_the_team_total(self):
        plant = case4.hourly_from_profile(case4.load_profile(), DATA.calendar, SPEC.capacity_kwp)
        self.assertAlmostEqual(plant.sum(), 767_489.3, delta=1.0)
        self.assertAlmostEqual(plant.sum() / SPEC.capacity_kwp, 1395.4, delta=0.1)   # same yield as the existing array

    def test_no_output_at_night_and_never_above_capacity(self):
        plant = case4.hourly_from_profile(case4.load_profile(), DATA.calendar, SPEC.capacity_kwp)
        night = (DATA.calendar.hour < 5) | (DATA.calendar.hour > 19)
        self.assertEqual(plant[night].max(), 0.0)
        self.assertLess(plant.max(), SPEC.capacity_kwp)

    def test_bad_profile_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "p.csv"
            pd.DataFrame({"hour": range(24), "Jan": 0.0}).to_csv(bad, index=False)
            with self.assertRaisesRegex(ValueError, "columns"):
                case4.load_profile(bad)
            good = pd.read_csv(case4.PROFILE_FILE)
            good.loc[5, "Feb"] = -1.0
            good.to_csv(bad, index=False)
            with self.assertRaisesRegex(ValueError, "between 0 and 1,200"):
                case4.load_profile(bad)

    def test_inconsistent_capacity_is_rejected(self):
        with self.assertRaises(ValueError):
            case4.PlantSpec(500.0, 1000, 0.55, 2.6, 15, 180, 14, 13.7, 100.5, "c-Si", "test")

    def test_plant_is_available(self):
        self.assertTrue(case4.plant_available())


class OffsiteSimulation(unittest.TestCase):
    c4 = case4.run_case4(DATA, CASES, SETTINGS)

    def test_energy_balance_every_hour(self):
        s = self.c4.scenario
        np.testing.assert_allclose(s.used_kw + s.grid_kw, s.load_kw, atol=1e-9)
        np.testing.assert_allclose(s.used_kw + s.export_kw, s.pv_kw, atol=1e-9)

    def test_the_building_still_buys_exactly_what_it_did_in_case3(self):
        np.testing.assert_allclose(self.c4.scenario.grid_kw, CASES.case3.grid_kw)
        np.testing.assert_allclose(self.c4.scenario.load_kw, CASES.case3.load_kw)
        self.assertAlmostEqual(self.c4.scenario.peak_onpeak_kw, CASES.case3.peak_onpeak_kw, places=9)

    def test_saving_is_the_credit_times_the_plant_energy(self):
        self.assertAlmostEqual(self.c4.saving_vs_case3_thb, 2.2 * self.c4.plant_kwh, delta=1.0)

    def test_reference_numbers(self):
        """Regression pin for the default credit (2.20 THB/kWh) and price (26,000 THB/kWp)."""
        self.assertAlmostEqual(self.c4.plant_kwh, 767_489.3, delta=1.0)
        self.assertAlmostEqual(self.c4.offset_share, 0.3855, places=3)
        self.assertAlmostEqual(self.c4.saving_vs_case3_thb, 1_688_476, delta=5)
        self.assertAlmostEqual(self.c4.vs_case3.capex_thb, 550 * 26_000)
        self.assertAlmostEqual(self.c4.vs_case3.payback_years, 9.25, places=2)

    def test_whole_programme_adds_up(self):
        self.assertAlmostEqual(self.c4.saving_vs_case1_thb, self.c4.saving_vs_case3_thb + CASES.total_saving_thb, places=4)
        self.assertAlmostEqual(self.c4.vs_case1.capex_thb, (74.25 + 550) * 26_000)

    def test_exports_stay_inside_the_transformer(self):
        self.assertFalse(self.c4.exceeds_transformer)

    def test_a_dearer_price_changes_the_capex_not_the_saving(self):
        dear = case4.run_case4(DATA, CASES, replace(SETTINGS, pv_cost_per_kwp=40_000.0))
        self.assertAlmostEqual(dear.saving_vs_case3_thb, self.c4.saving_vs_case3_thb, places=4)
        self.assertGreater(dear.vs_case3.payback_years, self.c4.vs_case3.payback_years)

    def test_zero_credit_never_pays_back(self):
        free = case4.run_case4(DATA, CASES, replace(SETTINGS, c4_credit=0.0))
        self.assertLess(free.saving_vs_case3_thb, 1_000)           # only the tiny roof surplus credit is lost
        self.assertIsNone(free.vs_case3.payback_years)

    def test_bad_inputs_are_rejected(self):
        load, roof, plant = CASES.case3.load_kw, self.c4.roof_pv_kw, self.c4.plant_kw
        with self.assertRaises(ValueError):
            case4.simulate_offsite(DATA, load, roof, plant, -0.1)
        with self.assertRaises(ValueError):
            case4.simulate_offsite(DATA, load, roof, plant[:-1], 2.2)
        with self.assertRaises(ValueError):
            case4.simulate_offsite(DATA, load, roof, -plant, 2.2)


class ValueOfTheCredit(unittest.TestCase):
    c4 = case4.run_case4(DATA, CASES, SETTINGS)

    def test_credit_options_are_ordered(self):
        table = case4.credit_options(DATA, CASES, self.c4, SETTINGS)
        none, buyback, retail = table["Saving vs Case 3"].tolist()
        self.assertLess(none, buyback)
        self.assertLess(buyback, retail)
        self.assertAlmostEqual(buyback, self.c4.saving_vs_case3_thb, delta=0.5)
        self.assertTrue(pd.isna(table["Payback (years)"].iloc[0]))
        self.assertLess(table["Payback (years)"].iloc[2], table["Payback (years)"].iloc[1])

    def test_credit_curve_is_exact(self):
        curve = case4.credit_curve(self.c4, SETTINGS)
        for i in (0, 9, 24):
            full = case4.simulate_offsite(DATA, CASES.case3.load_kw, self.c4.roof_pv_kw, self.c4.plant_kw, curve["credit"][i])
            self.assertAlmostEqual(curve["saving_thb"][i], self.c4.bill_case3_thb - full.bill.total_thb, delta=0.5)
        self.assertTrue((np.diff(curve["payback_years"].dropna()) <= 1e-9).all())   # a higher credit never lengthens payback


class HourlyExportCredit(unittest.TestCase):
    """The engine can credit exports at a different price in every hour (retail net metering)."""

    def test_flat_array_equals_flat_price(self):
        big = CASES.case3.pv_kw * 8.0
        load = CASES.case3.load_kw
        flat = simulate(load, big, DATA.calendar)
        hourly = simulate(load, big, DATA.calendar, export_rate=np.full(DATA.calendar.n_hours, 2.2))
        self.assertAlmostEqual(flat.bill.total_thb, hourly.bill.total_thb, places=6)
        self.assertGreater(flat.export_kwh, 0.0)

    def test_bad_hourly_credit_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate(CASES.case3.load_kw, CASES.case3.pv_kw, DATA.calendar, export_rate=np.ones(10))
        with self.assertRaises(ValueError):
            simulate(CASES.case3.load_kw, CASES.case3.pv_kw, DATA.calendar, export_rate=np.full(DATA.calendar.n_hours, -1.0))


if __name__ == "__main__":
    unittest.main()
