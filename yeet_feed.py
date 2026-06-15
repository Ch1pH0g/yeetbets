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

DATA = os.path.join(HERE, "data")
STATUS_CSV = os.path.join(DATA, "team_status.csv")
OUT_JSON = os.path.join(DATA, "yeet_feed.json")

# One CSV per bookmaker (all share the same export format). The label is what
# shows on each player's row; the file holds that book's bets.
BOOK_FILES = {
    "YEET": "YEET_BETS_updated.csv",
    "Bethog": "Bethog-bets.csv",
    "BOL": "BOL-bets.csv",
    "Stake": "Stake-bets.csv",
}

COMP = "https://api.football-data.org/v4/competitions/WC"
# football-data spellings differ from the books here and there; normalise on the
# CSV side. Extend as the diagnostics flag unmatched teams.
TEAM_ALIASES = {
    "new zeland": "New Zealand",
    "cape verde": "Cape Verde Islands",
    "czech republic": "Czechia",
    "bosnia & herzegovina": "Bosnia-Herzegovina",
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
def _name_key(name: str) -> str:
    """Loose key for matching the same player across books despite spelling
    (spaces, hyphens, case, accents): 'In-beom Hwang' == 'In Beom Hwang'."""
    return "".join(c for c in _norm(name) if c.isalnum())


def parse_books() -> dict:
    """Read every book CSV (Selection, Team, Unit stake) and aggregate by player.

    Returns {(_name_key, fd_team_norm): {name, country, fd_team, books}} where
    books is {book_label: total_stake} — one entry per player even if they were
    backed at several books.
    """
    players: dict = {}
    for book, fname in BOOK_FILES.items():
        path = os.path.join(DATA, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = (row.get("Selection") or "").strip()
                country = (row.get("Team") or "").strip()
                try:
                    stake = float(row.get("Unit stake") or row.get("Cost") or 0)
                except ValueError:
                    continue
                if not name or not country or not stake:
                    continue
                fd_team = TEAM_ALIASES.get(_norm(country), country)
                key = (_name_key(name), _norm(fd_team))
                p = players.setdefault(key, {
                    "name": name, "country": country, "fd_team": fd_team,
                    "books": {}})
                p["books"][book] = p["books"].get(book, 0.0) + stake
    return players


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


# --------------------------- per-player compute ---------------------------- #
def _match_player(name: str, fd_team: str, scorers: list[tuple[str, str, int]]):
    """(player_goals, rivals) where rivals = [(name, goals)] of team-mates who
    have scored. Team-constrained so a bare surname can't match another team."""
    nteam = _norm(fd_team)
    full = _norm(name)
    last = full.split()[-1] if full else ""

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


def _status(pg: int, rival_top: int, pending: bool) -> str:
    """Won / Lost / Pending. No odds in the data, so no P&L — a settled tie at
    the top still counts as Won (a dead-heat win, just no payout to compute)."""
    if pending:
        return "Pending"
    if pg > 0 and pg >= rival_top:        # sole or tied top scorer
        return "Won"
    return "Lost"


# ------------------------------- build ------------------------------------- #
def build_feed() -> dict:
    players = parse_books()
    overrides = load_overrides()
    scorers = fetch_scorers()
    live = fetch_team_has_fixtures()
    scorer_teams = {_norm(tm) for _, tm, _ in scorers}

    rows, unmatched_team = [], []
    for p in players.values():
        nteam = _norm(p["fd_team"])
        pg, rivals = _match_player(p["name"], p["fd_team"], scorers)
        rival_top = max((g for _, g in rivals), default=0)
        tied = [nm for nm, g in rivals if g == rival_top and rival_top]  # all at top
        rival_name = ", ".join(tied) if tied else "—"
        tie_count = len(tied)

        ov = overrides.get(nteam)
        pending = (ov == "in") if ov else live.get(nteam, True)
        status = _status(pg, rival_top, pending)

        if nteam not in scorer_teams and nteam not in live:
            unmatched_team.append(p["country"])

        books = sorted(({"book": b, "stake": round(s, 2)}
                        for b, s in p["books"].items()),
                       key=lambda x: -x["stake"])
        rows.append({
            "country": p["country"], "name": p["name"],
            "player_goals": pg, "rival_name": rival_name, "rival_goals": rival_top,
            "tie_count": tie_count, "status": status,
            "books": books, "total_stake": round(sum(p["books"].values()), 2),
        })

    rows.sort(key=lambda r: (r["country"], r["name"]))

    settled = [r for r in rows if r["status"] in ("Won", "Lost")]
    pending = [r for r in rows if r["status"] == "Pending"]
    feed = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "kpis": {
            "players": len(rows),
            "books": len({b["book"] for r in rows for b in r["books"]}),
            "total_staked": round(sum(r["total_stake"] for r in rows), 2),
            "pending_stake": round(sum(r["total_stake"] for r in pending), 2),
            "pending_count": len(pending),
            "settled_count": len(settled),
            "won_count": sum(1 for r in settled if r["status"] == "Won"),
            "lost_count": sum(1 for r in settled if r["status"] == "Lost"),
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
    print(f"[{feed['updated']}] {k['players']} players across {k['books']} books "
          f"-> {OUT_JSON}")
    print(f"  total staked ${k['total_staked']:,.0f} | pending ${k['pending_stake']:,.0f} "
          f"({k['pending_count']}) | settled {k['won_count']}W/{k['lost_count']}L")
    if feed.get("warnings"):
        print("  UNMATCHED TEAMS (add to TEAM_ALIASES): "
              + ", ".join(feed["warnings"]))
    if args.print:
        for r in feed["bets"]:
            tie = f" ({r['tie_count']})" if r["tie_count"] > 1 else ""
            books = ", ".join(f"{b['book']} ${b['stake']:,.0f}" for b in r["books"])
            print(f"  {r['country']:<16} {r['name']:<26} "
                  f"{r['player_goals']}g vs {r['rival_goals']}{tie:<5} "
                  f"{r['status']:<8} {books}")


if __name__ == "__main__":
    main()
