"""YEET top-team-scorer live dashboard (Streamlit).

Run locally:   streamlit run app.py
Deploy:        push to GitHub, point Streamlit Community Cloud at this file,
               and add FOOTBALL_DATA_API_KEY in the app's Secrets.

Data refreshes on its own every ~10 min via st.cache_data(ttl=600) — one shared
fetch regardless of how many people are watching.

The chart is a soccer-ball pictograph (one ball per goal) rendered as HTML/SVG —
green balls for the YEET pick, greyed balls for the team's top rival.
"""
from __future__ import annotations

import base64
import os

import pandas as pd
import streamlit as st

import yeet_feed

st.set_page_config(page_title="YEET · WC2026 top scorers", layout="centered",
                   page_icon="⚽")

# Streamlit Cloud puts the key in st.secrets; mirror it into env for yeet_feed.
# Locally there's no secrets.toml (st.secrets then raises), and load_env() in
# yeet_feed has already populated the var from .env — so this is best-effort.
if not os.environ.get("FOOTBALL_DATA_API_KEY"):
    try:
        os.environ["FOOTBALL_DATA_API_KEY"] = st.secrets["FOOTBALL_DATA_API_KEY"]
    except Exception:
        pass

# design system (shared with the Google Sheets look)
ACCENT, MUTED, INK, NAVY = "#1FA37C", "#8A94A6", "#243047", "#1B2A4A"
BAND, GRID, PAGE = "#F2F5FA", "#E6ECF4", "#E9EDF3"

# Flags keyed on the CSV country spelling (e.g. "New Zeland", "Cape Verde").
# Real flag glyphs on macOS/iOS/Android; Windows shows the two-letter code.
FLAGS = {
    "Algeria": "🇩🇿", "Argentina": "🇦🇷", "Australia": "🇦🇺", "Belgium": "🇧🇪",
    "Brazil": "🇧🇷", "Cape Verde": "🇨🇻", "Colombia": "🇨🇴", "Curacao": "🇨🇼",
    "Czechia": "🇨🇿", "Ecuador": "🇪🇨", "Egypt": "🇪🇬", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Germany": "🇩🇪", "Iran": "🇮🇷", "Iraq": "🇮🇶", "Ivory Coast": "🇨🇮",
    "Jordan": "🇯🇴", "Mexico": "🇲🇽", "Morocco": "🇲🇦", "New Zeland": "🇳🇿",
    "Panama": "🇵🇦", "Paraguay": "🇵🇾", "Saudi Arabia": "🇸🇦", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "Senegal": "🇸🇳", "South Africa": "🇿🇦", "South Korea": "🇰🇷", "Spain": "🇪🇸",
    "Sweden": "🇸🇪", "Tunisia": "🇹🇳", "Uruguay": "🇺🇾", "Uzbekistan": "🇺🇿",
}


def _ball_uri(fill: str, stroke: str) -> str:
    """A small soccer-ball SVG (white pattern on `fill`) as a data URI."""
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        f"<circle cx='50' cy='50' r='45' fill='{fill}' stroke='{stroke}' stroke-width='4'/>"
        f"<polygon points='50,28 68,41 61,62 39,62 32,41' fill='#FFFFFF'/>"
        f"<g stroke='#FFFFFF' stroke-width='5' stroke-linecap='round'>"
        f"<line x1='50' y1='28' x2='50' y2='7'/><line x1='68' y1='41' x2='87' y2='30'/>"
        f"<line x1='61' y1='62' x2='75' y2='82'/><line x1='39' y1='62' x2='25' y2='82'/>"
        f"<line x1='32' y1='41' x2='13' y2='30'/></g></svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


BALL_PICK = _ball_uri(ACCENT, "#15795B")
BALL_RIVAL = _ball_uri("#C2C9D4", "#9AA3B2")

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Roboto:wght@400;500&display=swap');

/* greyed page; content sits inside a single white card */
.stApp {{ background-color: {PAGE}; }}
.block-container {{
    background: #FFFFFF;
    border: 1px solid {GRID};
    border-radius: 16px;
    padding: 2.1rem 2.4rem 2.6rem;
    margin-top: 2.0rem; margin-bottom: 2.0rem;
    max-width: 860px;
    box-shadow: 0 8px 30px rgba(27,42,74,0.07);
}}
footer {{ visibility: hidden; }}

/* hero */
.hero-title {{ font-family:'Montserrat',sans-serif; font-weight:700; font-size:30px;
    color:{NAVY}; letter-spacing:-0.4px; line-height:1.1; }}
.hero-title b {{ color:{ACCENT}; font-weight:700; }}
.hero-sub {{ color:{MUTED}; font-size:13px; margin-top:4px; }}
.hero-rule {{ height:3px; width:54px; background:{ACCENT}; border-radius:3px;
    margin:12px 0 4px; }}

/* KPI metric cards */
div[data-testid="stMetric"] {{
    background:#FBFCFE; border:1px solid #EAF0F7; border-radius:12px;
    padding:14px 16px 12px; }}
div[data-testid="stMetricLabel"] p {{ color:{MUTED}; font-size:12px; font-weight:500; }}
div[data-testid="stMetricValue"] {{ color:{INK}; }}

/* soccer-ball pictograph */
.ball {{ display:inline-block; width:22px; height:22px; background-size:contain;
    background-repeat:no-repeat; vertical-align:middle; }}
.ball.pick {{ background-image:url("{BALL_PICK}"); }}
.ball.rival {{ background-image:url("{BALL_RIVAL}"); }}
.legend {{ display:flex; gap:22px; align-items:center; color:{MUTED};
    font-size:13px; margin:4px 0 10px; }}
.legend .ball {{ margin-right:7px; }}
.plist {{ display:flex; flex-direction:column; gap:2px; }}
.prow {{ display:flex; align-items:center; gap:10px; padding:7px 12px;
    border-radius:8px; }}
.prow.band {{ background:{BAND}; }}
.who {{ flex:0 0 46%; text-align:right; color:{INK}; font-size:13px; line-height:1.25; }}
.who b {{ font-weight:600; }}
.who .ctry {{ color:{MUTED}; font-weight:400; }}
.track {{ flex:1; display:flex; align-items:center; flex-wrap:wrap; gap:2px;
    min-height:26px; }}
.gap {{ display:inline-block; width:14px; }}
.none {{ color:{MUTED}; font-size:13px; }}
.tie {{ color:{INK}; font-weight:700; font-size:12px; margin-left:7px; }}
.money {{ color:{MUTED}; font-size:12px; margin-left:11px; white-space:nowrap; }}
</style>
"""


@st.cache_data(ttl=600, show_spinner="Fetching live goals…")
def get_feed():
    return yeet_feed.build_feed()


def money(x: float) -> str:
    return f"${x:,.0f}" if abs(x) >= 1000 else f"${x:,.2f}"


def kfmt(x: float) -> str:
    """$12.0k style for compact labels."""
    return f"${x/1000:.1f}k" if abs(x) >= 1000 else f"${x:.0f}"


def pictograph_html(df: pd.DataFrame) -> str:
    """One row per bet: flag + name, then green balls (pick) and grey balls (rival)."""
    rows = []
    for i, r in enumerate(df.itertuples()):
        band = "band" if i % 2 else ""
        flag = FLAGS.get(r.country, "")
        pg, rg = int(r.player_goals), int(r.rival_goals)
        balls = "<span class='ball pick'></span>" * pg
        if rg:
            balls += "<span class='gap'></span>" + "<span class='ball rival'></span>" * rg
        if not pg and not rg:
            balls = "<span class='none'>—</span>"
        tie = f"<span class='tie'>({r.tie_count})</span>" if r.tie_count > 1 else ""
        moneyt = f"<span class='money'>{money(r.stake)} → {kfmt(r.potential_return)}</span>"
        title = (f"{r.name} · {r.country} — YEET {pg} vs top rival {rg}"
                 f"  ·  odds {r.odds:g}  ·  {r.status}")
        rows.append(
            f"<div class='prow {band}' title=\"{title}\">"
            f"<div class='who'>{flag} <b>{r.name}</b> "
            f"<span class='ctry'>· {r.country}</span></div>"
            f"<div class='track'>{balls}{tie}{moneyt}</div></div>")
    legend = ("<div class='legend'>"
              "<span><span class='ball pick'></span>YEET pick</span>"
              "<span><span class='ball rival'></span>team's top rival</span></div>")
    return legend + "<div class='plist'>" + "".join(rows) + "</div>"


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    feed = get_feed()
    k = feed["kpis"]

    st.markdown(
        f"<div class='hero-title'><b>YEET</b> · World Cup 2026</div>"
        f"<div class='hero-rule'></div>"
        f"<div class='hero-sub'>Team top-scorer book · live from football-data.org "
        f"· updated {feed['updated']}</div>",
        unsafe_allow_html=True)
    st.write("")

    if feed.get("warnings"):
        st.warning("Unmatched teams (check spelling / TEAM_ALIASES): "
                   + ", ".join(feed["warnings"]))

    # ---- settled / pending widget -------------------------------------- #
    c1, c2, c3 = st.columns(3)
    c1.metric("Settled P&L", money(k["settled_pnl"]),
              f"{k['settled_count']} bets settled", delta_color="off")
    c2.metric("Pending stake (at risk)", money(k["pending_stake"]),
              f"{k['pending_count']} bets in play", delta_color="off")
    c3.metric("Total staked", money(k["total_staked"]))

    st.write("")

    # ---- filter (per viewer, independent) ------------------------------ #
    choice = st.radio("Show", ["All bets", "Pending", "Won", "Lost"],
                      horizontal=True, label_visibility="collapsed")
    df = pd.DataFrame(feed["bets"])
    if choice != "All bets":
        want = "Pending" if choice == "Pending" else choice.rstrip("s")
        df = df[df["status"] == want]
    if df.empty:
        st.info(f"No {choice.lower()} yet.")
        return

    # ---- soccer-ball pictograph (one ball per goal) -------------------- #
    st.markdown(pictograph_html(df), unsafe_allow_html=True)

    st.caption("Each ball = one goal · 🟢 YEET pick · ⚪ team's current top rival · "
               "(N) = team-mates tied for top · stake → potential return.")


if __name__ == "__main__":
    main()
