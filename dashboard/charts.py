"""Plotly figure builders. Each function returns a styled figure; none touches Streamlit.

Conventions
    * Money is passed in THB and converted here with the `Currency` object, so a chart
      always matches the sidebar currency.
    * One colour per entity (see theme.py) and one value axis per chart.
    * Every figure has a legend when it shows two or more series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import theme
from .engine import Economics
from .fmt import Currency

HOURS = list(range(24))
_GAP = dict(color=theme.SURFACE, width=1.5)   # thin surface-coloured outline = gap between fills


def _bar(x, y, name: str, color: str, unit: str) -> go.Bar:
    return go.Bar(
        x=x, y=y, name=name, marker=dict(color=color, line=_GAP),
        hovertemplate="%{y:,.1f} " + unit + "<extra>" + name + "</extra>",
    )


# --------------------------------------------------------------------------- bars
def stacked_months(table: pd.DataFrame, colors: dict[str, str], ytitle: str, unit: str, height: int = 360) -> go.Figure:
    """Monthly stacked bars; `table` has months as the index and one column per part."""
    fig = go.Figure([_bar(table.index, table[c], c, colors[c], unit) for c in table.columns])
    fig.update_layout(barmode="stack", hovermode="x unified", yaxis_title=ytitle, bargap=0.25)
    return theme.style_figure(fig, height=height)


def grouped_months(table: pd.DataFrame, colors: dict[str, str], ytitle: str, unit: str, height: int = 360) -> go.Figure:
    """Monthly grouped bars (e.g. grid import before and after)."""
    fig = go.Figure([_bar(table.index, table[c], c, colors[c], unit) for c in table.columns])
    fig.update_layout(barmode="group", hovermode="x unified", yaxis_title=ytitle, bargap=0.28, bargroupgap=0.06)
    return theme.style_figure(fig, height=height)


def bill_by_case(labels: list[str], bills_thb: list[float], colors: list[str], cur: Currency, height: int = 340) -> go.Figure:
    """Annual bill of each case as one bar, with the value written on the bar."""
    values = [cur.to_display(v) for v in bills_thb]
    fig = go.Figure(
        go.Bar(
            x=labels, y=values, marker=dict(color=colors, line=_GAP),
            text=[cur.money(v) for v in bills_thb], textposition="outside", textfont=dict(color=theme.INK),
            customdata=[cur.both(v) for v in bills_thb],
            hovertemplate="%{x}<br>%{customdata}<extra></extra>",
        )
    )
    fig.update_layout(yaxis_title=f"Annual bill ({cur.unit})", bargap=0.35)
    fig.update_yaxes(range=[0, max(values) * 1.15])
    return theme.style_figure(fig, height=height, legend=False)


def waterfall(labels: list[str], values_thb: list[float], cur: Currency, height: int = 340) -> go.Figure:
    """Annual saving build-up: each step adds to the running total, the last bar is the total (axis starts at zero)."""
    measures = ["relative"] * (len(labels) - 1) + ["total"]
    shown = [cur.to_display(v) for v in values_thb]
    fig = go.Figure(
        go.Waterfall(
            x=labels, y=shown, measure=measures,
            text=[cur.money(v) for v in values_thb], textposition="outside", textfont=dict(color=theme.INK),
            connector=dict(line=dict(color=theme.LINE, width=1)),
            increasing=dict(marker=dict(color=theme.PV_NEW)),
            decreasing=dict(marker=dict(color=theme.COST)),
            totals=dict(marker=dict(color=theme.SAVE)),
            hovertemplate="%{x}<br>%{y:,.0f} " + cur.unit + "<extra></extra>",
        )
    )
    fig.update_layout(yaxis_title=f"Annual saving ({cur.unit})")
    fig.update_yaxes(rangemode="tozero")
    return theme.style_figure(fig, height=height, legend=False)


def bill_parts_by_month(parts: pd.DataFrame, cur: Currency, height: int = 360) -> go.Figure:
    """Monthly bill split into demand+service, on-peak energy and off-peak energy (THB in, display currency out)."""
    shown = parts.apply(cur.to_display)
    fig = go.Figure(
        [
            go.Bar(
                x=shown.index, y=shown[c], name=c, marker=dict(color=theme.BILL_PART[c], line=_GAP),
                hovertemplate="%{y:,.0f} " + cur.unit + "<extra>" + c + "</extra>",
            )
            for c in parts.columns
        ]
    )
    fig.update_layout(barmode="stack", hovermode="x unified", yaxis_title=f"Monthly bill ({cur.unit})", bargap=0.25)
    return theme.style_figure(fig, height=height)


def donut(values: pd.Series, colors: dict[str, str], center_text: str, height: int = 340) -> go.Figure:
    """Share of annual energy by end use."""
    fig = go.Figure(
        go.Pie(
            labels=list(values.index), values=list(values.values), hole=0.62, sort=False,
            marker=dict(colors=[colors[k] for k in values.index], line=dict(color=theme.SURFACE, width=2)),
            textinfo="percent", textfont=dict(color=theme.BG, size=13),
            hovertemplate="%{label}<br>%{value:,.1f} MWh (%{percent})<extra></extra>",
        )
    )
    fig.add_annotation(text=center_text, x=0.5, y=0.5, showarrow=False, font=dict(color=theme.INK, size=15))
    fig.update_layout(legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center"))
    return theme.style_figure(fig, height=height, margin=dict(l=10, r=10, t=20, b=40))


def floor_bars(values: pd.Series, height: int = 340) -> go.Figure:
    """Annual MWh by floor (horizontal bars, floor 1 on top)."""
    fig = go.Figure(
        go.Bar(
            y=list(values.index), x=list(values.values), orientation="h",
            marker=dict(color=theme.END_USE["Air conditioning"], line=_GAP),
            text=[f"{v:,.0f}" for v in values.values], textposition="outside", textfont=dict(color=theme.INK_2),
            hovertemplate="%{y}: %{x:,.1f} MWh<extra></extra>",
        )
    )
    theme.style_figure(fig, height=height, legend=False, margin=dict(l=70, r=40, t=20, b=44))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(title="Annual energy (MWh)", showgrid=True, gridcolor=theme.LINE)
    return fig


# --------------------------------------------------------------------------- lines and areas
def profiles(series: dict[str, tuple[np.ndarray, str, str]], ytitle: str = "kW", height: int = 340,
             xtitle: str = "Hour of day") -> go.Figure:
    """24-hour profiles. `series` maps a name to (values, colour, dash)."""
    fig = go.Figure()
    for name, (values, color, dash) in series.items():
        fig.add_trace(
            go.Scatter(
                x=HOURS, y=values, name=name, mode="lines",
                line=dict(color=color, width=2.2, dash=dash),
                hovertemplate="%{y:,.1f} kW<extra>" + name + "</extra>",
            )
        )
    fig.update_layout(hovermode="x unified", yaxis_title=ytitle, xaxis_title=xtitle)
    fig.update_xaxes(dtick=3, range=[0, 23])
    return theme.style_figure(fig, height=height)


def day_type_panels(
    panels: list[tuple[str, dict[str, tuple[np.ndarray, str, str]]]], height: int = 360
) -> go.Figure:
    """Three side-by-side 24-hour panels (workdays, weekends, low-use workdays)."""
    fig = make_subplots(rows=1, cols=len(panels), subplot_titles=[p[0] for p in panels], horizontal_spacing=0.07)
    for col, (_, series) in enumerate(panels, start=1):
        for name, (values, color, dash) in series.items():
            fig.add_trace(
                go.Scatter(
                    x=HOURS, y=values, name=name, mode="lines", legendgroup=name, showlegend=(col == 1),
                    line=dict(color=color, width=2.1, dash=dash),
                    hovertemplate="%{y:,.1f} kW<extra>" + name + "</extra>",
                ),
                row=1, col=col,
            )
    fig.update_xaxes(dtick=6, range=[0, 23], title_text="Hour")
    fig.update_yaxes(title_text="kW", col=1)
    fig.update_annotations(font=dict(color=theme.INK, size=13))
    return theme.style_figure(fig, height=height)


def duration(curves: dict[str, tuple[np.ndarray, np.ndarray, str]], height: int = 340) -> go.Figure:
    """Load-duration curves: kW that is exceeded for a given share of the year."""
    fig = go.Figure()
    for name, (x, y, color) in curves.items():
        fig.add_trace(
            go.Scatter(
                x=x, y=y, name=name, mode="lines", line=dict(color=color, width=2.2),
                hovertemplate="%{y:,.0f} kW exceeded %{x:.1f}% of the year<extra>" + name + "</extra>",
            )
        )
    fig.update_layout(xaxis_title="% of the year", yaxis_title="kW")
    return theme.style_figure(fig, height=height)


def week(index: pd.DatetimeIndex, load: np.ndarray, pv_existing: np.ndarray, pv_new: np.ndarray,
         grid: np.ndarray, weekend: np.ndarray, height: int = 400,
         names: tuple[str, str] = ("PV existing array", "PV new array"),
         export: np.ndarray | None = None) -> go.Figure:
    """One week, hour by hour: stacked PV (two parts), building load and grid import. Weekends are shaded.

    `names` labels the two PV parts; `export` (kW sent to the grid) adds a line when given.
    """
    fig = go.Figure()
    # shade weekend days
    day = index.normalize()
    for d in pd.unique(day[weekend]):
        fig.add_vrect(x0=d, x1=d + pd.Timedelta(days=1), fillcolor=theme.SURFACE_2, opacity=0.9, line_width=0, layer="below")
    fig.add_trace(go.Scatter(x=index, y=pv_existing, name=names[0], mode="lines", stackgroup="pv",
                             line=dict(width=0.6, color=theme.PV_OLD), fillcolor="rgba(155,114,230,0.55)",
                             hovertemplate="%{y:,.1f} kW<extra>" + names[0] + "</extra>"))
    fig.add_trace(go.Scatter(x=index, y=pv_new, name=names[1], mode="lines", stackgroup="pv",
                             line=dict(width=0.6, color=theme.PV_NEW), fillcolor="rgba(194,132,15,0.65)",
                             hovertemplate="%{y:,.1f} kW<extra>" + names[1] + "</extra>"))
    fig.add_trace(go.Scatter(x=index, y=load, name="Building load", mode="lines",
                             line=dict(color=theme.LOAD, width=2, dash="dot"),
                             hovertemplate="%{y:,.0f} kW<extra>Load</extra>"))
    fig.add_trace(go.Scatter(x=index, y=grid, name="Grid import", mode="lines",
                             line=dict(color=theme.GRID, width=2.2),
                             hovertemplate="%{y:,.0f} kW<extra>Grid</extra>"))
    if export is not None:
        fig.add_trace(go.Scatter(x=index, y=export, name="Export to grid", mode="lines",
                                 line=dict(color=theme.SAVE, width=2.2),
                                 hovertemplate="%{y:,.0f} kW<extra>Export</extra>"))
    fig.update_layout(hovermode="x unified", yaxis_title="kW")
    return theme.style_figure(fig, height=height)


def cumulative_cashflow(econ: Economics, cur: Currency, label: str, color: str, height: int = 340) -> go.Figure:
    """Cumulative cash position over the analysis horizon, with the break-even year marked."""
    years = np.arange(len(econ.cashflows_thb))
    cumulative = [cur.to_display(v) for v in econ.cumulative_thb]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=years, y=cumulative, name=label, mode="lines+markers",
            line=dict(color=color, width=2.6), marker=dict(size=6, color=color, line=dict(color=theme.SURFACE, width=1.5)),
            hovertemplate="Year %{x}: %{y:,.0f} " + cur.unit + "<extra>" + label + "</extra>",
        )
    )
    fig.add_hline(y=0, line=dict(color=theme.MUTED, width=1, dash="dot"))
    if econ.payback_years:
        fig.add_vline(x=econ.payback_years, line=dict(color=theme.INK_2, width=1, dash="dash"),
                      annotation_text=f"Payback {econ.payback_years:.1f} y", annotation_font=dict(color=theme.INK_2, size=12),
                      annotation_position="top right")
    fig.update_layout(xaxis_title="Year", yaxis_title=f"Cumulative cash ({cur.unit})")
    return theme.style_figure(fig, height=height, legend=False)


# --------------------------------------------------------------------------- heatmaps
def heatmap(z: np.ndarray, x_labels: list[str], colorscale, zlabel: str, height: int = 380,
            x_title: str = "") -> go.Figure:
    """Hour-of-day (rows) by month or weekday (columns)."""
    fig = go.Figure(
        go.Heatmap(
            z=z, x=x_labels, y=HOURS, colorscale=colorscale, xgap=2, ygap=1,
            colorbar=dict(title=dict(text=zlabel, font=dict(color=theme.INK_2)), tickfont=dict(color=theme.INK_2), thickness=12),
            hovertemplate="%{x}, %{y}:00<br>%{z:,.1f} " + zlabel + "<extra></extra>",
        )
    )
    fig.update_yaxes(title="Hour of day", dtick=3, showgrid=False)
    fig.update_xaxes(title=x_title)
    return theme.style_figure(fig, height=height, legend=False)


def saving_grid(table_thb: pd.DataFrame, cur: Currency, height: int = 330) -> go.Figure:
    """Annual saving for every combination of lighting cut (columns) and AC cut (rows)."""
    shown = table_thb.apply(cur.to_display)
    fig = go.Figure(
        go.Heatmap(
            z=shown.values, x=list(shown.columns), y=list(shown.index), colorscale=theme.RAMP_TEAL, xgap=3, ygap=3,
            text=[[cur.money(v) for v in row] for row in table_thb.values], texttemplate="%{text}",
            textfont=dict(color=theme.INK, size=13), showscale=False,
            hovertemplate="Lighting cut %{x}, AC cut %{y}<br>%{text} per year<extra></extra>",
        )
    )
    fig.update_xaxes(title="Lighting cut off-hours", showgrid=False)
    fig.update_yaxes(title="AC cut off-hours", showgrid=False)
    return theme.style_figure(fig, height=height, legend=False)


# --------------------------------------------------------------------------- Case 4
def credit_payback(curve: pd.DataFrame, marks: dict[str, float], chosen: float, height: int = 340) -> go.Figure:
    """Payback of the off-site plant against the credit paid for its energy, with named credits marked."""
    fig = go.Figure(
        go.Scatter(
            x=curve["credit"], y=curve["payback_years"], mode="lines", line=dict(color=theme.CASE_COLOR[4], width=2.6),
            hovertemplate="Credit %{x:.2f} THB/kWh: payback %{y:.1f} years<extra></extra>",
        )
    )
    for label, value in marks.items():
        fig.add_vline(x=value, line=dict(color=theme.MUTED, width=1, dash="dot"),
                      annotation_text=label, annotation_font=dict(color=theme.INK_2, size=11),
                      annotation_position="top right" if value < chosen + 1e-9 else "top left")
    fig.add_vline(x=chosen, line=dict(color=theme.INK, width=1.5, dash="dash"))
    fig.update_layout(xaxis_title="Credit for the plant's energy (THB/kWh)", yaxis_title="Payback of the plant (years)")
    fig.update_yaxes(rangemode="tozero")
    return theme.style_figure(fig, height=height, legend=False)


# --------------------------------------------------------------------------- Case 4 teaser
def sizing_line(df: pd.DataFrame, y_col: str, ytitle: str, convert, color: str, hover_unit: str,
                current_total_kwp: float, height: int = 320) -> go.Figure:
    """One metric against total PV size (snapshot of the Excel sizing sweep)."""
    x = df["total_kwp"]
    y = [convert(v) for v in df[y_col]]
    fig = go.Figure(
        go.Scatter(
            x=x, y=y, mode="lines+markers", line=dict(color=color, width=2.4),
            marker=dict(size=8, color=color, line=dict(color=theme.SURFACE, width=2)),
            hovertemplate="%{x:,.0f} kWp: %{y:,.1f} " + hover_unit + "<extra></extra>",
        )
    )
    fig.add_vline(x=current_total_kwp, line=dict(color=theme.INK_2, width=1, dash="dash"),
                  annotation_text="Planned plant", annotation_font=dict(color=theme.INK_2, size=12),
                  annotation_position="top left")
    fig.update_layout(xaxis_title="Total PV (kWp)", yaxis_title=ytitle)
    return theme.style_figure(fig, height=height, legend=False)
