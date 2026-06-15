"""Build the top-team-scorer feed for a fixed, curated list of picks.

Same shape and live-data logic as yeet_feed.build_feed(), but the players come
from the hardcoded PICKS list below instead of the bookmaker CSVs — and there
are no stakes/books (this view tracks goals only). Reuses yeet_feed's live
football-data helpers so the goals / rival / settlement logic is identical.

    python picks_feed.py            # writes data/picks_feed.json
    python picks_feed.py --print    # also dump a readable summary

Importable: build_picks_feed() returns the dict picks_app.py renders.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import yeet_feed
from yeet_feed import (_norm, _match_player, _status, TEAM_ALIASES,
                       fetch_scorers, fetch_team_has_fixtures, load_overrides)

OUT_JSON = os.path.join(yeet_feed.DATA, "picks_feed.json")

# Curated list — (player, country as you'd say it). Country is normalised to
# football-data's spelling via yeet_feed.TEAM_ALIASES for the goal match.
PICKS: list[tuple[str, str]] = [
    ("Thomas Meunier", "Belgium"),
    ("Yazan Al-Arab", "Jordan"),
    ("Rafik Belghali", "Algeria"),
    ("Brandon Mechele", "Belgium"),
    ("Ronald Araujo", "Uruguay"),
    ("Roberto Lopes", "Cape Verde"),
    ("Abdukodir Khusanov", "Uzbekistan"),
    ("Jose Maria Gimenez", "Uruguay"),
    ("Shojae Khalilzadeh", "Iran"),
    ("Ramy Bensebaini", "Algeria"),
    ("Timothy Castagne", "Belgium"),
    ("Ramin Rezaeian", "Iran"),
    ("Husam Abu Dahab", "Jordan"),
    ("Saed Al-Rosan", "Jordan"),
    ("Tommy Smith", "New Zealand"),
    ("Callan Elliot", "New Zealand"),
    ("Salim Obaid", "Jordan"),
    ("Mohammad Abu Hashish", "Jordan"),
    ("Nicolas Tagliafico", "Argentina"),
    ("Aissa Mandi", "Algeria"),
    ("Abdallah Nasib", "Jordan"),
    ("Gabriel Magalhaes", "Brazil"),
    ("Ali Nemati", "Iran"),
    ("Andrew Robertson", "Scotland"),
    ("Emmanuel Agbadou", "Ivory Coast"),
    ("Azizjon Ganiev", "Uzbekistan"),
    ("Ihsan Haddad", "Jordan"),
    ("Facundo Pellistri", "Uruguay"),
    ("Rayan Ait-Nouri", "Algeria"),
    ("Davinson Sanchez", "Colombia"),
    ("Diney", "Cape Verde"),
    ("Amadou Onana", "Belgium"),
    ("Ramon Sosa", "Paraguay"),
    ("Jefferson Lerma", "Colombia"),
    ("Nizar Al-Rashdan", "Jordan"),
    ("Aria Yousefi", "Iran"),
]


def build_picks_feed() -> dict:
    overrides = load_overrides()
    scorers = fetch_scorers()
    live = fetch_team_has_fixtures()
    scorer_teams = {_norm(tm) for _, tm, _ in scorers}

    rows, unmatched_team = [], []
    for name, country in PICKS:
        fd_team = TEAM_ALIASES.get(_norm(country), country)
        nteam = _norm(fd_team)
        pg, rivals = _match_player(name, fd_team, scorers)
        rival_top = max((g for _, g in rivals), default=0)
        tied = [nm for nm, g in rivals if g == rival_top and rival_top]
        rival_name = ", ".join(tied) if tied else "—"

        ov = overrides.get(nteam)
        pending = (ov == "in") if ov else live.get(nteam, True)
        status = _status(pg, rival_top, pending)

        if nteam not in scorer_teams and nteam not in live:
            unmatched_team.append(country)

        rows.append({
            "country": country, "name": name,
            "player_goals": pg, "rival_name": rival_name, "rival_goals": rival_top,
            "tie_count": len(tied), "status": status,
        })

    rows.sort(key=lambda r: (r["country"], r["name"]))

    settled = [r for r in rows if r["status"] in ("Won", "Lost")]
    pending = [r for r in rows if r["status"] == "Pending"]
    feed = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "kpis": {
            "players": len(rows),
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

    feed = build_picks_feed()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)

    k = feed["kpis"]
    print(f"[{feed['updated']}] {k['players']} picks -> {OUT_JSON}")
    print(f"  pending {k['pending_count']} | settled {k['won_count']}W/{k['lost_count']}L")
    if feed.get("warnings"):
        print("  UNMATCHED TEAMS (add to yeet_feed.TEAM_ALIASES): "
              + ", ".join(feed["warnings"]))
    if args.print:
        for r in feed["bets"]:
            tie = f" ({r['tie_count']})" if r["tie_count"] > 1 else ""
            print(f"  {r['country']:<16} {r['name']:<26} "
                  f"{r['player_goals']}g vs {r['rival_goals']}{tie:<5} {r['status']}")


if __name__ == "__main__":
    main()
