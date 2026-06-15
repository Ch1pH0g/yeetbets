"""Curated picks · top-team-scorer live dashboard (Streamlit).

Same look and feel as the YEET app (app.py) — per-team cards, soccer-ball
goal pictograph, live standing chips — but for the fixed PICKS list in
picks_feed.py and with NO stakes/books (goal tracking only).

Run locally:   streamlit run picks_app.py
Deploy:        push to a Streamlit Community Cloud app pointed at this file and
               add FOOTBALL_DATA_API_KEY in its Secrets.
"""
from __future__ import annotations

import base64
import os

import pandas as pd
import streamlit as st

import picks_feed

REFRESH_S = 300   # live_view auto-reruns this often (st.fragment run_every)

st.set_page_config(page_title="Curated Top Goalscorer Picks · WC2026",
                   layout="centered", page_icon="⚽")

# Streamlit Cloud puts the key in st.secrets; mirror it into env for the feed.
if not os.environ.get("FOOTBALL_DATA_API_KEY"):
    try:
        os.environ["FOOTBALL_DATA_API_KEY"] = st.secrets["FOOTBALL_DATA_API_KEY"]
    except Exception:
        pass

# design system (shared with the Google Sheets / YEET app look)
ACCENT, MUTED, INK, NAVY = "#1FA37C", "#8A94A6", "#243047", "#1B2A4A"
BAND, GRID, PAGE = "#F2F5FA", "#E6ECF4", "#E9EDF3"

# Flags keyed on the team spelling used in players.py (football-data names).
# Real flag glyphs on macOS/iOS/Android; Windows shows the two-letter code.
FLAGS = {
    "Algeria": "🇩🇿", "Argentina": "🇦🇷", "Australia": "🇦🇺", "Belgium": "🇧🇪",
    "Brazil": "🇧🇷", "Cape Verde Islands": "🇨🇻", "Colombia": "🇨🇴", "Croatia": "🇭🇷",
    "Germany": "🇩🇪", "Ghana": "🇬🇭", "Iran": "🇮🇷", "Ivory Coast": "🇨🇮",
    "Japan": "🇯🇵", "Jordan": "🇯🇴", "Morocco": "🇲🇦", "New Zealand": "🇳🇿",
    "Paraguay": "🇵🇾", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "South Korea": "🇰🇷", "Spain": "🇪🇸",
    "Switzerland": "🇨🇭", "Tunisia": "🇹🇳", "United States": "🇺🇸", "Uruguay": "🇺🇾",
    "Uzbekistan": "🇺🇿",
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

/* per-team cards */
.ball {{ display:inline-block; width:18px; height:18px; background-size:contain;
    background-repeat:no-repeat; vertical-align:middle; margin-right:1px; }}
.ball.pick {{ background-image:url("{BALL_PICK}"); }}
.zero {{ color:{MUTED}; font-size:13px; }}
.team {{ border:1px solid #EAF0F7; border-radius:12px; margin-bottom:12px;
    overflow:hidden; }}
.team-hd {{ display:flex; align-items:center; gap:8px; background:{BAND};
    padding:8px 14px; font-weight:600; color:{INK}; font-size:14px; }}
.team-hd .cnt {{ margin-left:auto; color:{MUTED}; font-weight:400; font-size:12px; }}
.pk {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px 10px;
    padding:8px 14px; border-top:1px solid #F0F3F8; font-size:13px; }}
.pk-name {{ flex:0 0 36%; color:{INK}; font-weight:500; }}
.pk-goals {{ flex:0 0 auto; min-width:20px; }}
.pk-stand {{ flex:1 1 auto; display:flex; align-items:center; gap:7px; flex-wrap:wrap; }}
.chip {{ font-size:11px; font-weight:600; padding:2px 9px; border-radius:999px;
    white-space:nowrap; }}
.chip.lead, .chip.won {{ background:#E4F4EA; color:#1E7E45; }}
.chip.behind, .chip.lost {{ background:#FBE7E6; color:#C5221F; }}
.chip.tie {{ background:#FCEFC7; color:#8A6D1F; }}
.chip.none {{ background:#EEF1F5; color:#5F6B7A; }}
.vs {{ color:{MUTED}; font-size:12px; }}
</style>
"""


@st.cache_data(ttl=270, show_spinner="Fetching live goals…")
def get_feed():
    return picks_feed.build_picks_feed()


def standing(status: str, pg: int, rg: int) -> tuple[str, str]:
    """(chip_class, label): settlement once settled, else live standing vs the
    best other scorer on the team."""
    if status == "Won":
        return "won", "✅ Won"
    if status == "Lost":
        return "lost", "❌ Lost"
    if pg > rg:
        return "lead", "Leading"
    if pg == rg and pg > 0:
        return "tie", "Tied"
    if pg == 0 and rg == 0:
        return "none", "No goals yet"
    return "behind", f"{rg - pg} behind"


def team_tables_html(df: pd.DataFrame, country_asc: bool = True) -> str:
    """One card per team; a row per pick showing goals, live standing and the
    rival to beat (no stakes — goal tracking only)."""
    df = df.sort_values(["country", "player_goals", "name"],
                        ascending=[country_asc, False, True])
    blocks = []
    for country, g in df.groupby("country", sort=False):
        flag = FLAGS.get(country, "")
        picks = []
        for r in g.itertuples():
            pg, rg = int(r.player_goals), int(r.rival_goals)
            cls, label = standing(r.status, pg, rg)
            goals = ("<span class='ball pick'></span>" * pg if pg
                     else "<span class='zero'>0</span>")
            vs = f"<span class='vs'>vs {r.rival_name} ({rg})</span>" if rg else ""
            picks.append(
                f"<div class='pk'>"
                f"<div class='pk-name'>{r.name}</div>"
                f"<div class='pk-goals'>{goals}</div>"
                f"<div class='pk-stand'><span class='chip {cls}'>{label}</span>{vs}</div>"
                f"</div>")
        n = len(g)
        blocks.append(
            f"<div class='team'><div class='team-hd'>{flag} {country}"
            f"<span class='cnt'>{n} pick{'s' if n > 1 else ''}</span></div>"
            + "".join(picks) + "</div>")
    return "".join(blocks)


@st.fragment(run_every=REFRESH_S)
def live_view():
    """As a fragment with run_every, Streamlit re-runs just this every
    REFRESH_S, so a page left open updates itself with no full reload."""
    feed = get_feed()
    k = feed["kpis"]

    st.markdown(
        f"<div class='hero-sub'>{k['players']} picks · "
        f"live from football-data.org · updated {feed['updated']} · "
        f"auto-refreshes every ~5 min</div>",
        unsafe_allow_html=True)
    st.write("")

    if feed.get("warnings"):
        st.warning("Teams not in football-data's WC feed (shown but not tracked): "
                   + ", ".join(feed["warnings"]))

    # ---- counts widget (no stakes in this view) ------------------------ #
    c1, c2, c3 = st.columns(3)
    c1.metric("Picks", k["players"], "players tracked", delta_color="off")
    c2.metric("Pending", k["pending_count"], "teams still in play", delta_color="off")
    c3.metric("Settled", f"{k['won_count']}W · {k['lost_count']}L",
              f"of {k['settled_count']} settled", delta_color="off")

    st.write("")

    # ---- filters (per viewer, independent) ----------------------------- #
    choice = st.radio("Show", ["All picks", "Pending", "Won", "Lost"],
                      horizontal=True, label_visibility="collapsed")
    df = pd.DataFrame(feed["bets"])
    if choice != "All picks":
        df = df[df["status"] == choice]

    countries = sorted(df["country"].unique())
    fc1, fc2, fc3 = st.columns([3, 3, 2])
    picked = fc1.multiselect("Country", countries, placeholder="All countries")
    query = fc2.text_input("Search player", placeholder="player or country…")
    order = fc3.selectbox("Sort", ["A → Z", "Z → A"])

    if picked:
        df = df[df["country"].isin(picked)]
    if query:
        q = query.strip()
        df = df[df["name"].str.contains(q, case=False, na=False)
                | df["country"].str.contains(q, case=False, na=False)]
    if df.empty:
        st.info("No picks match those filters.")
        return

    # ---- per-team tables ----------------------------------------------- #
    st.markdown(team_tables_html(df, country_asc=(order == "A → Z")),
                unsafe_allow_html=True)

    st.caption("Each green ball = a goal by the pick · standing is vs the team's "
               "best other scorer (\"vs …\") · 🟢 leading · 🟡 tied · 🔴 behind · "
               "✅/❌ once the team is out.")


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        "<div class='hero-title'><b>Top Goalscorer Picks</b> · World Cup 2026</div>"
        "<div class='hero-rule'></div>", unsafe_allow_html=True)
    live_view()


if __name__ == "__main__":
    main()
