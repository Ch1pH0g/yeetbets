"""Build the YEET bespoke top-team-scorer feed.

Reads data/YEET_BETS.csv (one "Top Team Scorer" bet per row), pulls live goals
from football-data.org, and computes everything the dashboard needs per bet:
current goals, the top rival on the same national team, how many team-mates are
tied at that rival tally, the settlement state (Won / Lost / Pending) and P&L.

Settlement is HYBRID: a team is Pending while it still has a non-FINISHED
fixture, unless data/team_status.csv forces it in/out (for the group->knockout
edge cases the fixture list can't resolve cleanly). Top-scorer ties pay the
standard dead-heat reduction: return = stake * odds / (players tied at top).

    python yeet_feed.py                 # writes data/yeet_feed.json
    python yeet_feed.py --print         # also dump a readable summary

Importable: build_feed() returns the dict the Streamlit app renders.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import unicodedata
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(__file__)


def load_env(path: str | None = None) -> None:
    """Minimal .env loader (KEY=VALUE lines) into os.environ. No-op on hosts
    like Streamlit Cloud where there's no .env — the key comes from secrets."""
    path = path or os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


load_env()

BETS_CSV = os.path.join(HERE, "data", "YEET_BETS.csv")
STATUS_CSV = os.path.join(HERE, "data", "team_status.csv")
OUT_JSON = os.path.join(HERE, "data", "yeet_feed.json")

COMP = "https://api.football-data.org/v4/competitions/WC"
# football-data spellings differ from the CSV here and there; normalise on the
# CSV side. Extend as the diagnostics flag unmatched teams.
TEAM_ALIASES = {
    "new zeland": "New Zealand",
    "cape verde": "Cape Verde Islands",
}
# fixture statuses that mean the team still has football to play
LIVE_STATUSES = {"SCHEDULED", "TIMED", "IN_PLAY", "PAUSED", "SUSPENDED", "POSTPONED"}


# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    """Lower-case, accent-stripped, trimmed — for fuzzy name/team matching."""
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c)).lower().strip()


def _api_get(path: str, **params):
    key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not key:
        raise RuntimeError("FOOTBALL_DATA_API_KEY not set (.env or environment).")
    r = requests.get(f"{COMP}/{path}", params=params,
                     headers={"X-Auth-Token": key}, timeout=30)
    r.raise_for_status()
    return r.json()


# ------------------------------- inputs ------------------------------------ #
def parse_bets(path: str = BETS_CSV) -> list[dict]:
    """Parse 'Country - Surname, First', stake, decimal odds.

    Handles mononyms with no comma ('Brazil - Marquinhos') and applies the
    team-name alias map so the football-data lookup matches.
    """
    bets = []
    with open(path, encoding="utf-8") as f:
        for raw in csv.reader(f):
            if len(raw) < 3:
                continue
            label, stake_s, odds_s = raw[0], raw[1], raw[2]
            try:
                stake, odds = float(stake_s), float(odds_s)
            except ValueError:
                continue  # header row ("1, Stake, Odds (Decimal)")
            if " - " not in label:
                continue
            country, name = (p.strip() for p in label.split(" - ", 1))
            if "," in name:
                surname, first = (p.strip() for p in name.split(",", 1))
            else:
                surname, first = name, ""           # mononym
            fd_team = TEAM_ALIASES.get(_norm(country), country)
            bets.append({
                "country": country, "fd_team": fd_team,
                "name": name, "surname": surname, "first": first,
                "stake": stake, "odds": odds,
            })
    return bets


def load_overrides(path: str = STATUS_CSV) -> dict:
    """team_status.csv -> {normalised team: 'in'|'out'}. Optional file."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            team = (row.get("team") or "").strip()
            status = (row.get("status") or "").strip().lower()
            if team and status in ("in", "out"):
                out[_norm(team)] = status
    return out


# ----------------------------- live data ----------------------------------- #
def fetch_scorers() -> list[tuple[str, str, int]]:
    data = _api_get("scorers", limit=100)
    return [(s.get("player", {}).get("name", ""),
             s.get("team", {}).get("name", ""),
             s.get("goals") or 0) for s in data.get("scorers", [])]


def fetch_team_has_fixtures() -> dict:
    """{normalised team name: True if it still has a non-FINISHED match}."""
    live = {}
    for m in _api_get("matches").get("matches", []):
        playing = m.get("status") in LIVE_STATUSES
        for side in ("homeTeam", "awayTeam"):
            nm = _norm((m.get(side) or {}).get("name", ""))
            if nm:
                live[nm] = live.get(nm, False) or playing
    return live


# --------------------------- per-bet compute ------------------------------- #
def _match_player(bet: dict, scorers: list[tuple[str, str, int]]):
    """(player_goals, rivals) where rivals = [(name, goals)] of team-mates who
    have scored. Team-constrained so a bare surname can't match another team."""
    nteam = _norm(bet["fd_team"])
    full = _norm(f"{bet['first']} {bet['surname']}")
    last = _norm(bet["surname"]).split()[-1] if bet["surname"] else ""

    def is_pick(nm: str) -> bool:
        n = _norm(nm)
        return n == full or (bool(last) and last in n)

    pg, rivals = 0, []
    for nm, tm, g in scorers:
        if _norm(tm) != nteam:
            continue
        if is_pick(nm):
            pg = max(pg, g)
        else:
            rivals.append((nm, g))
    return pg, rivals


def _settle(pg: int, rivals: list, stake: float, odds: float, pending: bool):
    """Returns (status, tie_count, deadheat_d, pnl, potential_return).

    tie_count = team-mates sharing the top rival tally (the '(N)' badge, shown
    when >1). On settlement, a tie at the top pays odds / (players tied)."""
    rival_top = max((g for _, g in rivals), default=0)
    tie_count = sum(1 for _, g in rivals if g == rival_top and rival_top > 0)
    potential = stake * odds

    if pending:
        return "Pending", tie_count, 0, 0.0, potential

    if pg > rival_top and pg > 0:                     # sole top scorer
        return "Won", tie_count, 1, stake * (odds - 1), potential
    if pg == rival_top and pg > 0:                    # dead heat at the top
        d = tie_count + 1                            # rivals tied + our pick
        return "Won", tie_count, d, stake * odds / d - stake, potential / d
    return "Lost", tie_count, 0, -stake, potential   # beaten, or nobody scored


# ------------------------------- build ------------------------------------- #
def build_feed() -> dict:
    bets = parse_bets()
    overrides = load_overrides()
    scorers = fetch_scorers()
    live = fetch_team_has_fixtures()
    scorer_teams = {_norm(tm) for _, tm, _ in scorers}

    rows, unmatched_team = [], []
    for b in bets:
        nteam = _norm(b["fd_team"])
        pg, rivals = _match_player(b, scorers)
        rival_top = max((g for _, g in rivals), default=0)
        tied = [nm for nm, g in rivals if g == rival_top and rival_top]  # all at top
        rival_name = ", ".join(tied) if tied else "—"

        ov = overrides.get(nteam)
        if ov:
            pending = ov == "in"
        else:
            pending = live.get(nteam, True)          # default to pending if unknown

        status, tie_count, d, pnl, potential = _settle(
            pg, rivals, b["stake"], b["odds"], pending)

        if nteam not in scorer_teams and nteam not in live:
            unmatched_team.append(b["country"])

        rows.append({
            "country": b["country"], "name": b["name"],
            "stake": b["stake"], "odds": b["odds"],
            "player_goals": pg, "rival_name": rival_name, "rival_goals": rival_top,
            "tie_count": tie_count, "status": status,
            "deadheat_d": d, "pnl": round(pnl, 2),
            "potential_return": round(potential, 2),
        })

    # country A->Z, then name Z->A within country (stable two-pass sort)
    rows.sort(key=lambda r: r["name"], reverse=True)
    rows.sort(key=lambda r: r["country"])

    settled = [r for r in rows if r["status"] in ("Won", "Lost")]
    pending = [r for r in rows if r["status"] == "Pending"]
    feed = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "kpis": {
            "settled_pnl": round(sum(r["pnl"] for r in settled), 2),
            "settled_count": len(settled),
            "pending_stake": round(sum(r["stake"] for r in pending), 2),
            "pending_potential_return": round(sum(r["potential_return"] for r in pending), 2),
            "pending_count": len(pending),
            "total_staked": round(sum(r["stake"] for r in rows), 2),
        },
        "bets": rows,
    }
    if unmatched_team:
        feed["warnings"] = sorted(set(unmatched_team))
    return feed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="dump a readable summary")
    args = ap.parse_args()

    feed = build_feed()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)

    k = feed["kpis"]
    print(f"[{feed['updated']}] {len(feed['bets'])} bets -> {OUT_JSON}")
    print(f"  settled P&L ${k['settled_pnl']:,.2f} ({k['settled_count']} bets) | "
          f"pending ${k['pending_stake']:,.0f} staked, "
          f"${k['pending_potential_return']:,.0f} potential ({k['pending_count']} live)")
    if feed.get("warnings"):
        print("  UNMATCHED TEAMS (add to TEAM_ALIASES): "
              + ", ".join(feed["warnings"]))
    if args.print:
        for r in feed["bets"]:
            tie = f" ({r['tie_count']})" if r["tie_count"] > 1 else ""
            print(f"  {r['country']:<14} {r['name']:<28} "
                  f"{r['player_goals']}g vs {r['rival_goals']}{tie:<5} "
                  f"{r['status']:<8} ${r['pnl']:>10,.2f}")


if __name__ == "__main__":
    main()
