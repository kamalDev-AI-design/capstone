"""Presentation helpers: CSS + small HTML components. No business logic."""
import html

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
/* Streamlit's fixed header is ~60px tall; keep content clear of it on every page. */
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 5rem !important; max-width: 1280px; }
header[data-testid="stHeader"] { background: rgba(11,18,32,.88); backdrop-filter: blur(6px); }
.psit-banner { background: linear-gradient(90deg,#134e4a 0%,#1e3a5f 100%); border:1px solid #2dd4bf55;
  border-radius: 12px; padding: 10px 16px; font-size: .85rem; color:#d7f5ef; margin-bottom: 14px; display:flex; justify-content:space-between; gap:12px; align-items:center;}
.psit-title { font-size: 1.9rem; font-weight: 700; margin: 0 0 2px 0;
  background: linear-gradient(90deg,#2dd4bf,#60a5fa); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.psit-sub { color:#8da2c0; margin-bottom: 18px; }
.psit-card { background:#111a2e; border:1px solid #22304d; border-radius:14px; padding:16px 18px; }
.psit-kpi { background: linear-gradient(145deg,#111a2e,#15213a); border:1px solid #22304d; border-radius:14px; padding:14px 18px; }
.psit-kpi .v { font-size:2rem; font-weight:700; line-height:1.1; }
.psit-kpi .l { font-size:.75rem; letter-spacing:.06em; word-spacing:.25em; text-transform:uppercase; color:#8da2c0; }
.pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem; font-weight:600; letter-spacing:.04em; }
.pill-NEW { background:#1d4ed855; color:#93c5fd; border:1px solid #3b82f6; }
.pill-IN_REVIEW { background:#b4530955; color:#fcd34d; border:1px solid #f59e0b; }
.pill-CLOSED { background:#04785755; color:#6ee7b7; border:1px solid #10b981; }
.pill-type { background:#4c1d9555; color:#c4b5fd; border:1px solid #8b5cf6; }
.pill-SOP { background:#0e749055; color:#67e8f9; border:1px solid #06b6d4; }
.pill-REPORT { background:#9d174d55; color:#f9a8d4; border:1px solid #ec4899; }
.ref { font-family: ui-monospace, Consolas, monospace; font-weight:600; color:#2dd4bf; }
.stepper { display:flex; align-items:center; gap:0; margin: 8px 0 14px 0; }
.step { padding:8px 16px; border-radius:999px; background:#16223a; border:1px solid #22304d; color:#8da2c0; font-weight:600; font-size:.8rem;}
.step.done { background:#04785733; color:#6ee7b7; border-color:#10b981; }
.step.active { background:#2dd4bf22; color:#2dd4bf; border-color:#2dd4bf; box-shadow:0 0 12px #2dd4bf44; }
.bar { height:2px; width:36px; background:#22304d; } .bar.done { background:#10b981; }
.tl { border-left:2px solid #22304d; margin-left:6px; padding-left:16px; }
.tl-item { position:relative; margin-bottom:14px; } .tl-item:before { content:''; position:absolute; left:-23px; top:5px; width:10px; height:10px; border-radius:50%; background:#2dd4bf; }
.tl-item.denied:before { background:#f87171; }
.muted { color:#8da2c0; font-size:.8rem; }
.alert-warn { background:#78350f44; border:1px solid #f59e0b; border-radius:10px; padding:10px 14px; }
.alert-ok { background:#06402944; border:1px solid #10b981; border-radius:10px; padding:10px 14px; }
.alert-bad { background:#7f1d1d44; border:1px solid #ef4444; border-radius:10px; padding:10px 14px; }
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(s) -> str:
    return html.escape(str(s))


def pill(status: str) -> str:
    return f'<span class="pill pill-{esc(status)}">{esc(status.replace("_", " "))}</span>'


def type_label(t: str) -> str:
    return "Adverse Event" if t == "SUSPECTED_ADVERSE_EVENT" else "Quality Complaint"


def kpi(label: str, value, color: str = "#e6edf7") -> str:
    return f'<div class="psit-kpi"><div class="l">{esc(label)}</div><div class="v" style="color:{color}">{esc(value)}</div></div>'


def stepper(status: str) -> str:
    order = ["NEW", "IN_REVIEW", "CLOSED"]
    idx = order.index(status)
    parts = []
    for i, s in enumerate(order):
        cls = "active" if i == idx else ("done" if i < idx else "")
        parts.append(f'<div class="step {cls}">{s.replace("_", " ")}</div>')
        if i < len(order) - 1:
            parts.append(f'<div class="bar {"done" if i < idx else ""}"></div>')
    return f'<div class="stepper">{"".join(parts)}</div>'


def header(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="psit-title">{esc(title)}</div><div class="psit-sub">{esc(subtitle)}</div>', unsafe_allow_html=True)


def alert(kind: str, text: str) -> None:
    st.markdown(f'<div class="alert-{kind}">{text}</div>', unsafe_allow_html=True)
