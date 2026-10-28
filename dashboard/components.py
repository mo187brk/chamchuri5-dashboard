"""Reusable Streamlit building blocks: hero, page header, KPI cards, note panels, tables.

All dynamic text is HTML-escaped before it is placed in a markup string; the only HTML
that reaches `st.markdown(..., unsafe_allow_html=True)` is built here from trusted
templates plus escaped values.
"""

from __future__ import annotations

import base64
import html
import inspect
import re
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
import streamlit as st

from . import theme
from .config import ASSETS_DIR

_BOLD = re.compile(r"\*\*(.+?)\*\*")

# Streamlit renamed `use_container_width=True` to `width="stretch"`; pick whichever this version knows.
_STRETCH_PLOTLY = (
    {"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters else {"use_container_width": True}
)


def _dataframe(df: pd.DataFrame) -> None:
    try:
        st.dataframe(df, width="stretch")
    except (TypeError, ValueError):
        st.dataframe(df, use_container_width=True)


def _inline(text: str) -> str:
    """Escape text, then turn **bold** markers into <b> tags."""
    return _BOLD.sub(r"<b>\1</b>", html.escape(text))


@lru_cache(maxsize=None)
def image_data_uri(name: str) -> str:
    """Embed an image from ./assets as a data URI so no static file server is needed."""
    raw = (ASSETS_DIR / name).read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")


def inject_theme() -> None:
    """Inject the page CSS once per run."""
    st.markdown(f"<style>{theme.CSS}</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- hero and headers
@dataclass(frozen=True)
class CaseChip:
    label: str
    color: str
    live: bool = True


def _chips_html(chips: list[CaseChip]) -> str:
    parts = []
    for chip in chips:
        state = "live" if chip.live else "pending"
        parts.append(
            f'<span class="chip {state}"><span class="dot" style="background:{chip.color}"></span>'
            f"{html.escape(chip.label)}</span>"
        )
    return '<div class="chip-row">' + "".join(parts) + "</div>"


def hero(title: str, subtitle: str, chips: list[CaseChip], photo: str = "building_photo.jpg") -> None:
    """Front-page banner with the building photograph."""
    st.markdown(
        '<section class="hero">'
        '<div class="hero-text">'
        f"{_chips_html(chips)}"
        f'<h1 class="hero-title">{html.escape(title)}</h1>'
        f'<p class="hero-sub">{html.escape(subtitle)}</p>'
        "</div>"
        f'<div class="hero-photo" style="background-image:url(\'{image_data_uri(photo)}\')">'
        '<span class="hero-credit">Chamchuri 5, Chulalongkorn University</span></div>'
        "</section>",
        unsafe_allow_html=True,
    )


def page_header(chip: CaseChip, title: str, subtitle: str) -> None:
    st.markdown(
        '<div class="page-head">'
        f"{_chips_html([chip])}"
        f"<h1>{html.escape(title)}</h1>"
        f"<p>{html.escape(subtitle)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def section(title: str, caption: str | None = None) -> None:
    st.markdown(f"## {title}")
    if caption:
        st.caption(caption)


# --------------------------------------------------------------------------- KPI cards
@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    sub: str = ""
    tone: str = theme.LINE
    delta: str = ""
    delta_warn: bool = False


def _kpi_html(k: Kpi) -> str:
    delta = ""
    if k.delta:
        cls = "kpi-delta warn" if k.delta_warn else "kpi-delta"
        delta = f'<div class="{cls}">{html.escape(k.delta)}</div>'
    sub = f'<div class="kpi-sub">{_inline(k.sub)}</div>' if k.sub else ""
    return (
        f'<div class="kpi" style="--tone:{k.tone}">'
        f'<div class="kpi-label">{html.escape(k.label)}</div>'
        f'<div class="kpi-value">{html.escape(k.value)}</div>'
        f"{sub}{delta}</div>"
    )


def kpi_row(kpis: list[Kpi], per_row: int = 4) -> None:
    """Lay KPI cards out in rows of `per_row` equal columns."""
    for start in range(0, len(kpis), per_row):
        chunk = kpis[start:start + per_row]
        columns = st.columns(per_row)
        for column, kpi in zip(columns, chunk):
            with column:
                st.markdown(_kpi_html(kpi), unsafe_allow_html=True)
        st.markdown('<div style="height:0.7rem"></div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- notes
def _note_html(title: str, items: list[str]) -> str:
    bullets = "".join(f"<li>{_inline(item)}</li>" for item in items)
    return f'<div class="note"><h4>{html.escape(title)}</h4><ul>{bullets}</ul></div>'


def note_panels(applied: list[str], results: list[str], notes: list[str]) -> None:
    """The three-column 'what was applied / results / notes' block closing every case page."""
    st.markdown("## Notes for this case")
    a, b, c = st.columns(3)
    with a:
        st.markdown(_note_html("What was applied", applied), unsafe_allow_html=True)
    with b:
        st.markdown(_note_html("Results", results), unsafe_allow_html=True)
    with c:
        st.markdown(_note_html("Read with care", notes), unsafe_allow_html=True)


def callout(text: str, kind: str = "info") -> None:
    """A short boxed remark. kind: info | warn | good."""
    if kind not in ("info", "warn", "good"):
        raise ValueError(f"Unknown callout kind {kind!r}")
    st.markdown(f'<div class="callout {kind}">{_inline(text)}</div>', unsafe_allow_html=True)


def photo_figure(name: str, caption: str) -> None:
    st.markdown(
        '<figure class="fig-photo" style="margin:0">'
        f'<img src="{image_data_uri(name)}" alt="{html.escape(caption)}"/>'
        f"<figcaption>{html.escape(caption)}</figcaption></figure>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- charts and tables
def show(fig, key: str) -> None:
    """Render a Plotly figure with the app's theme (key must be unique on the page)."""
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False}, **_STRETCH_PLOTLY)


def data_table(df: pd.DataFrame, key: str, filename: str, label: str = "Table view") -> None:
    """Every chart has a table equivalent plus a CSV download."""
    with st.expander(label):
        _dataframe(df)
        st.download_button(
            "Download CSV", df.to_csv().encode("utf-8"), file_name=filename, mime="text/csv", key=f"dl_{key}"
        )


def table(df: pd.DataFrame) -> None:
    """A visible (not collapsed) table."""
    _dataframe(df)


def case_card(chip: CaseChip, title: str, text: str, figure: str, figure_sub: str) -> None:
    """Overview card: one case, one headline number."""
    state = "" if chip.live else " pending"
    st.markdown(
        f'<div class="case-card{state}">{_chips_html([chip])}'
        f"<h3>{html.escape(title)}</h3><p>{html.escape(text)}</p>"
        f'<div class="figure">{html.escape(figure)}</div>'
        f'<div class="figure-sub">{html.escape(figure_sub)}</div></div>',
        unsafe_allow_html=True,
    )
