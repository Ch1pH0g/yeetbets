"""YEET top-team-scorer live dashboard (Streamlit).

Run locally:   streamlit run app.py
Deploy:        push to GitHub, point Streamlit Community Cloud at this file,
               and add FOOTBALL_DATA_API_KEY in the app's Secrets.

Data refreshes on its own every ~10 min via st.cache_data(ttl=600) — one shared
fetch regardless of how many people are watching.
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
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
POS, NEG = "#1E7E45", "#C5221F"

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
div[data-testid="stMetricLabel"] p {{ color:{MUTED}; font-size:12px;
    font-weight:500; }}
div[data-testid="stMetricValue"] {{ color:{INK}; }}
</style>
"""


@st.cache_data(ttl=600, show_spinner="Fetching live goals…")
def get_feed():
    return yeet_feed.build_feed()


def money(x: float) -> str:
    return f"${x:,.0f}" if abs(x) >= 1000 else f"${x:,.2f}"


def kfmt(x: float) -> str:
    """$12.0k style for compact bar labels."""
    return f"${x/1000:.1f}k" if abs(x) >= 1000 else f"${x:.0f}"


def row_label(name: str, country: str) -> str:
    """Flag + player + muted country (HTML, rendered by Plotly tick labels)."""
    flag = FLAGS.get(country, "")
    return f"{flag} {name}  <span style='color:{MUTED}'>· {country}</span>".strip()


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

    # ---- grouped bars: YEET's pick vs the team's top rival ------------- #
    df = df.assign(label=[row_label(n, c) for n, c in zip(df["name"], df["country"])])

    def end_text(r):
        tie = f"  ({r.tie_count})" if r.tie_count > 1 else ""
        return f"{int(r.player_goals)}{tie}   {money(r.stake)} → {kfmt(r.potential_return)}"

    pick = go.Bar(
        name="YEET pick", y=df["label"], x=df["player_goals"], orientation="h",
        marker=dict(color=ACCENT), text=[end_text(r) for r in df.itertuples()],
        textposition="outside", textfont=dict(color=INK, size=11),
        cliponaxis=False, customdata=df[["name", "country", "odds", "pnl"]],
        hovertemplate=("<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                       "YEET pick: %{x} goals<br>Odds: %{customdata[2]}<br>"
                       "P&L: $%{customdata[3]:,.2f}<extra></extra>"))
    rlabel = ["Top rivals" if t > 1 else "Top rival" for t in df["tie_count"]]
    rival = go.Bar(
        name="Team's top rival", y=df["label"], x=df["rival_goals"],
        orientation="h", marker=dict(color=MUTED),
        customdata=df.assign(rlabel=rlabel)[["rlabel", "rival_name"]],
        hovertemplate=("%{customdata[0]} on %{x}: %{customdata[1]}<extra></extra>"))

    # x-axis floor so a lone 1-goal bar doesn't stretch full-width, but kept
    # tight so we don't waste width while goals are still low
    top = int(max(df["player_goals"].max(), df["rival_goals"].max(), 0))
    xmax = max(4, top + 1)
    xmax += xmax % 2

    fig = go.Figure([pick, rival])
    order = list(df["label"])[::-1]   # feed is country A->Z, name Z->A; top row first
    fig.update_yaxes(categoryorder="array", categoryarray=order,
                     tickfont=dict(color=INK, size=12))
    # zebra banding — one band per player (covers both its bars), full width
    fig.update_layout(shapes=[
        dict(type="rect", xref="paper", yref="y", x0=0, x1=1,
             y0=i - 0.5, y1=i + 0.5, fillcolor=BAND, line_width=0, layer="below")
        for i in range(len(order)) if i % 2 == 0])
    fig.update_layout(
        barmode="group", bargap=0.22, bargroupgap=0.06, barcornerradius=3,
        height=110 + 30 * len(df), margin=dict(l=10, r=150, t=8, b=34),
        xaxis_title="Goals", yaxis_title=None,
        font=dict(family="Roboto", color=INK),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID,
                        font=dict(family="Roboto", color=INK)),
    )
    fig.update_xaxes(range=[0, xmax], dtick=1, gridcolor=GRID,
                     zerolinecolor=GRID, title_font=dict(size=12, color=MUTED))
    st.plotly_chart(fig, width="stretch",
                    config={"displayModeBar": False})

    st.caption("🟢 YEET pick · ⚪ team's current top rival · "
               "label = goals, (N) team-mates tied for top, stake → potential return.")


if __name__ == "__main__":
    main()
