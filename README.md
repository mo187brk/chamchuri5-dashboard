# Chamchuri 5 · Solar and Savings Dashboard

An interactive Streamlit dashboard that prices the hourly 2019 electricity load of Chamchuri 5, a research office tower at Chulalongkorn University (Bangkok), on the MEA Type 3.2 TOU tariff, and compares four cases.

| Case | Description |
|---|---|
| 1 · Today | The building as received, with the existing 20 kWp rooftop array |
| 2 · New solar | Case 1 plus a new 74.25 kWp array on the free half of the roof |
| 3 · Solar + rules | Case 2 plus two off-hours rules: lighting and air-conditioning cuts |
| 4 · What-if | Hypothetical 550 kWp plant on open land, exported to the grid and credited on the building's bill (virtual net metering) |

Each page shows the key results, charts, and notes on what was applied and how to read the numbers. Currency can be switched between THB and USD.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important notes

- **Case 4 is an assumption, not a real project.** It supposes that other land was found, since the roof has no more space. The credit price for exported energy is an input, and the result depends strongly on it. Land, grid connection, wheeling fees and the legal basis of net metering are not modelled.
- Equipment prices, finance parameters and the lighting and air-conditioning cut percentages are **assumptions** to be replaced with quotes and pilot results.
- The existing 20 kWp array is estimated from a satellite image (±25%); no PV output was metered.
- PV output uses a typical day for each month, without day-to-day weather variation.

## Project structure

```
app.py              entry point: sidebar and navigation
dashboard/          calculation engine, page views, charts and theme
data/               input data: hourly load, PV profiles, reference results
tests/              unit tests (python -m unittest discover -s tests -t .)
```

## Data source

Load data: Pipattanasomporn et al., *CU-BEMS, a smart building electricity consumption and indoor environmental sensor dataset*, Scientific Data 7:241 (2020), licensed CC BY 4.0.
