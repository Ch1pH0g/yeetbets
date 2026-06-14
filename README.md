# YEET · World Cup 2026 — team top-scorer book

A live dashboard tracking a book of "Top Team Scorer" bets through WC2026: each
pick's current goals vs the team's top rival, settlement (Won / Lost / Pending)
and P&L, with stake and potential return.

## Run locally
```bash
pip install -r requirements.txt
export FOOTBALL_DATA_API_KEY=your-key      # or put it in a .env file
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)
Point a new app at `app.py` and add `FOOTBALL_DATA_API_KEY` in the app's
**Secrets** (TOML): `FOOTBALL_DATA_API_KEY = "your-key"`. Data self-refreshes
every ~10 min via `st.cache_data`.

## Files
- `app.py` — the Streamlit dashboard.
- `yeet_feed.py` — pulls football-data.org and computes the per-bet feed.
- `data/YEET_BETS.csv` — the bets (`Country - Surname, First`, stake, decimal odds).
- `data/team_status.csv` — manual settlement override (`team,status` in/out).

Data: [football-data.org](https://www.football-data.org/).
