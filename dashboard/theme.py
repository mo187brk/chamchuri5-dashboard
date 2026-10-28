"""Visual identity: colour tokens, page CSS and the shared Plotly layout.

Palette notes
    The five series colours were validated for the dark chart surface (#101C2E) with the
    data-viz palette validator: lightness band, chroma floor, colour-blind separation of
    adjacent pairs and 3:1 contrast all pass. Each colour belongs to ONE entity everywhere
    in the app (amber is always the new PV array, blue is always the grid, and so on).
"""

from __future__ import annotations

# ---- surfaces and ink --------------------------------------------------------
BG = "#0B1626"          # page
SURFACE = "#101C2E"     # cards and chart surface
SURFACE_2 = "#16263D"   # raised elements
LINE = "#243651"        # borders and gridlines
INK = "#E8EDF5"         # primary text
INK_2 = "#A9B6C9"       # secondary text
MUTED = "#7D8CA5"       # captions

# ---- series colours (one entity, one colour) ---------------------------------
PV_NEW = "#C2840F"      # amber: the new array and solar in general
PV_OLD = "#9B72E6"      # violet: the existing array
GRID = "#4A90E2"        # blue: energy bought from the grid
SAVE = "#17A589"        # teal: savings and the demand-side rules
COST = "#E5645E"        # coral: money, cost, warnings about cost
LOAD = "#A8B3C5"        # neutral: building load

# One colour per case, used for chips, lines and bars that stand for a whole case.
CASE_COLOR = {1: LOAD, 2: PV_NEW, 3: SAVE, 4: MUTED}

# End uses are parts of one entity (the building load), so they are tints of one slate hue.
END_USE = {"Air conditioning": "#5E7BA6", "Lighting": "#9DB4D3", "Plug loads": "#D3DEEC"}
# Parts of the electricity bill: tints of one coral hue, darkest at the stack base.
BILL_PART = {"Demand and service": "#B84A45", "On-peak energy": "#E5645E", "Off-peak energy": "#F4B0AC"}
# Savings by end use: tints of the savings hue.
SAVING_USE = {"Air conditioning": "#17A589", "Lighting": "#7FDCC4"}

# Colour ramps for magnitude (dark = low, light = high on the dark surface).
RAMP_BLUE = [[0.0, "#14304F"], [0.4, "#1F5A94"], [0.75, "#3B88D6"], [1.0, "#9CC8F5"]]
RAMP_TEAL = [[0.0, "#12353A"], [0.4, "#157A6A"], [0.75, "#17A589"], [1.0, "#86E3CB"]]
RAMP_AMBER = [[0.0, "#2A2418"], [0.4, "#7A5A12"], [0.75, "#C2840F"], [1.0, "#F2CC6E"]]

# Accent used for text on dark (series colours are for marks, not for text).
ACCENT_TEXT = "#E9B44C"

FONT_DISPLAY = "'Bricolage Grotesque', 'Segoe UI', system-ui, sans-serif"
FONT_BODY = "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif"

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {{
  --bg: {BG}; --surface: {SURFACE}; --surface-2: {SURFACE_2}; --line: {LINE};
  --ink: {INK}; --ink-2: {INK_2}; --muted: {MUTED};
  --pv: {PV_NEW}; --pv-old: {PV_OLD}; --grid: {GRID}; --save: {SAVE}; --cost: {COST}; --load: {LOAD};
  --accent-text: {ACCENT_TEXT};
}}

html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {{
  background: var(--bg);
  font-family: {FONT_BODY};
  color: var(--ink);
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: var(--surface); border-right: 1px solid var(--line); }}
[data-testid="stSidebar"] * {{ font-family: {FONT_BODY}; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1240px; }}

h1, h2, h3, h4 {{ font-family: {FONT_DISPLAY}; letter-spacing: -0.01em; color: var(--ink); }}
h2 {{ font-size: 1.55rem; margin-top: 2.2rem; }}
h3 {{ font-size: 1.15rem; }}
p, li {{ line-height: 1.6; }}
a {{ color: var(--accent-text); }}

/* ---- hero ---- */
.hero {{
  display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  min-height: 360px; border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
  background: var(--surface);
}}
.hero-text {{ padding: 2.4rem 2.4rem 2rem; display: flex; flex-direction: column; justify-content: center; gap: 1rem; }}
.hero-title {{
  font-family: {FONT_DISPLAY}; font-weight: 700; font-size: 2.7rem; line-height: 1.05;
  letter-spacing: -0.025em; margin: 0; color: var(--ink);
}}
.hero-sub {{ color: var(--ink-2); font-size: 1.05rem; max-width: 34rem; margin: 0; }}
.hero-photo {{
  position: relative; background-size: cover; background-position: center 35%;
  min-height: 260px;
}}
.hero-photo::before {{
  content: ""; position: absolute; inset: 0;
  background: linear-gradient(90deg, var(--surface) 0%, rgba(16,28,46,0.0) 38%),
              linear-gradient(0deg, rgba(11,22,38,0.55) 0%, rgba(11,22,38,0) 45%);
}}
.hero-credit {{ position: absolute; right: 12px; bottom: 8px; font-size: 0.72rem; color: var(--ink-2); }}

/* ---- chips ---- */
.chip-row {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
.chip {{
  display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.22rem 0.7rem;
  border: 1px solid var(--line); border-radius: 999px; font-size: 0.82rem; color: var(--ink-2);
  background: var(--surface-2);
}}
.chip .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.chip.live {{ color: var(--ink); }}
.chip.pending {{ border-style: dashed; color: var(--muted); }}

/* ---- page header ---- */
.page-head {{ margin: 0 0 1.4rem; }}
.page-head h1 {{ font-size: 2.2rem; font-weight: 700; margin: 0.5rem 0 0.3rem; line-height: 1.1; }}
.page-head p {{ color: var(--ink-2); margin: 0; max-width: 46rem; }}

/* ---- KPI cards ---- */
.kpi {{
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 0.95rem 1.05rem 0.9rem; height: 100%; position: relative; overflow: hidden;
}}
.kpi::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--tone, var(--line)); }}
.kpi-label {{ color: var(--ink-2); font-size: 0.84rem; margin-bottom: 0.25rem; }}
.kpi-value {{ font-family: {FONT_DISPLAY}; font-weight: 700; font-size: 1.75rem; line-height: 1.1; color: var(--ink); font-variant-numeric: tabular-nums; }}
.kpi-sub {{ color: var(--muted); font-size: 0.8rem; margin-top: 0.3rem; line-height: 1.4; }}
.kpi-delta {{ display: inline-block; margin-top: 0.4rem; font-size: 0.78rem; padding: 0.1rem 0.5rem; border-radius: 999px; background: rgba(23,165,137,0.16); color: #7EE0C6; }}
.kpi-delta.warn {{ background: rgba(229,100,94,0.16); color: #F4A29D; }}

/* ---- note panels ---- */
.note {{
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 1rem 1.2rem; height: 100%;
}}
.note h4 {{ margin: 0 0 0.6rem; font-size: 1rem; }}
.note ul {{ margin: 0; padding-left: 1.1rem; color: var(--ink-2); font-size: 0.92rem; }}
.note li {{ margin-bottom: 0.4rem; }}
.note li b {{ color: var(--ink); font-weight: 600; }}

/* ---- callouts ---- */
.callout {{
  border: 1px solid var(--line); border-left-width: 4px; border-radius: 8px;
  padding: 0.8rem 1rem; background: var(--surface); margin: 0.6rem 0 1rem; font-size: 0.93rem; color: var(--ink-2);
}}
.callout b {{ color: var(--ink); }}
.callout.info {{ border-left-color: var(--grid); }}
.callout.warn {{ border-left-color: var(--pv); }}
.callout.good {{ border-left-color: var(--save); }}

/* ---- figures ---- */
.fig-photo {{ border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface); }}
.fig-photo img {{ width: 100%; display: block; max-height: 430px; object-fit: cover; object-position: center 45%; }}
.fig-photo figcaption {{ padding: 0.55rem 0.8rem; font-size: 0.8rem; color: var(--muted); }}

.case-card {{
  background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 1.1rem 1.2rem; height: 100%;
}}
.case-card.pending {{ border-style: dashed; background: transparent; }}
.case-card h3 {{ margin: 0.6rem 0 0.3rem; font-size: 1.1rem; }}
.case-card p {{ color: var(--ink-2); font-size: 0.9rem; margin: 0 0 0.7rem; }}
.case-card .figure {{ font-family: {FONT_DISPLAY}; font-weight: 700; font-size: 1.35rem; }}
.case-card .figure-sub {{ color: var(--muted); font-size: 0.8rem; }}

.stTabs [data-baseweb="tab"] {{ font-family: {FONT_BODY}; }}
.brand {{ font-family: {FONT_DISPLAY}; font-weight: 700; font-size: 1.25rem; letter-spacing: -0.01em; }}
.brand small {{ display: block; font-family: {FONT_BODY}; font-weight: 400; font-size: 0.78rem; color: var(--muted); letter-spacing: 0; }}

@media (max-width: 900px) {{
  .hero {{ grid-template-columns: 1fr; }}
  .hero-photo {{ min-height: 220px; order: -1; }}
  .hero-photo::before {{ background: linear-gradient(0deg, var(--surface) 0%, rgba(16,28,46,0) 55%); }}
  .hero-title {{ font-size: 2.1rem; }}
}}
"""


def style_figure(fig, height: int = 380, legend: bool = True, margin: dict | None = None):
    """Apply the shared dark layout to a Plotly figure and return it."""
    fig.update_layout(
        height=height,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", color=INK_2, size=13),
        margin=margin or dict(l=56, r=20, t=44, b=44),
        showlegend=legend,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(color=INK_2, size=12), bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor=SURFACE_2, bordercolor=LINE, font=dict(color=INK, size=13),
        ),
        title=dict(text=None),
    )
    fig.update_xaxes(
        showgrid=False, zeroline=False, linecolor=LINE, tickcolor=LINE,
        tickfont=dict(color=INK_2, size=12), title_font=dict(color=INK_2, size=12),
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=LINE, gridwidth=1, zeroline=False, linecolor=LINE,
        tickfont=dict(color=INK_2, size=12), title_font=dict(color=INK_2, size=12),
    )
    return fig
