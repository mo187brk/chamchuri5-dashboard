# Chamchuri 5 · Solar and savings dashboard

Streamlit dashboard for the Chamchuri 5 rooftop-solar study (Chulalongkorn University, Bangkok).
It prices the measured 2019 hourly load on the MEA Type 3.2 TOU tariff and compares four cases.

| Case | What it is | Status |
|---|---|---|
| 1 · Today | The building as received, with the existing 20 kWp array | live |
| 2 · New solar | Case 1 plus a new 74.25 kWp array on the free half of the roof | live |
| 3 · Solar + rules | Case 2 plus two off-hours rules (lighting and air-conditioning cuts) | live |
| 4 · What-if | 550 kWp plant on other land, exported and credited on the bill (virtual net metering) | live, hypothetical |

## Run it (VS Code terminal, from this folder)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

## Check it

```bash
python -m unittest discover -s tests -t .
```

The tests reproduce the Excel strategy model (bills of Cases 1 and 2, PV energy, peak demand,
payback, NPV, IRR and the first cash-flow years) and check the engine's invariants. The app smoke
test runs only when Streamlit and Plotly are installed.

## Controls (sidebar)

* **Currency**: THB or USD, with an editable exchange rate (default 33.78 THB/USD, quote of 2026-10-27).
* **Solar assumptions**: orientation of the new array (as supplied or south-facing) and the PV price.
* **Off-hours rules**: lighting cut, air-conditioning cut, working hours, optional "low-use workdays are holidays",
  and the cost of implementing the rules (zero until estimated).

Off-hours are all weekend hours, plus workdays before the start and from the end of the working hours.

## Case 4: the what-if

Case 4 is an explicit assumption: the roof has no room left, so suppose open land was found, a 550 kWp plant was
built there, all of its output is exported to the grid and its energy is credited on the building's bill.
The building's own grid import and billed demand do not change; only the credit does.

* The plant data ships in `data/case4_plant.json` and `data/case4_plant_profile.csv` (typical day per month, Wh/kWp).
* The credit price (sidebar, "Case 4 what-if") decides the result: default 2.20 THB/kWh (Thai buy-back);
  the page also shows no credit and the retail TOU price as bounds.
* Not modelled: land cost, grid connection, wheeling fees, the legal basis of net metering.
* Optional: put `data/case4_expanded.csv` (`datetime,pv_expanded_kw`, 8,760 rows) to replace the monthly profile
  with an hourly series. It is validated first and a clear message appears if it is wrong.

## Layout

```
app.py                  entry point: sidebar and navigation
dashboard/config.py     every assumption in one place (tariff, plant, finance, rules)
dashboard/engine.py     pure calculation: calendar, PV, tariff bill, rules, cash flows
dashboard/model.py      turns settings into Cases 1-3
dashboard/case4.py      Case 4 what-if: plant data, off-site simulation, credit sensitivity
dashboard/views/        one module per page
dashboard/charts.py     Plotly figure builders;  theme.py / components.py: look and UI blocks
data/                   shipped inputs (hourly year, sizing snapshots, Excel reference numbers)
scripts/build_data.py   rebuilds ./data from the Excel model and the hourly load CSV
tests/                  reconciliation with Excel, invariants, Case 4 what-if, app smoke test
```

## Status labels used in the app

MEASURED and SUPPLIED values come from project files. ESTIMATED (existing 20 kWp, ±25%), MODELLED
(typical-day PV profile) and ASSUMED (prices, finance, the two cut percentages) need confirmation.
The Methodology page lists them and shows a live reconciliation with the Excel model.
