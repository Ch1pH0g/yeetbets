"""Single source of truth for the team top-scorer picks.

Plain data, no dependencies — so it can be imported by both the Google Sheet
sync (gsheet_sync.py) and the standalone Streamlit picks app (picks_feed.py),
and shipped into the dashboard-only `yeetbets` repo without dragging in gspread
or any service-account code.

(name, team) — team uses football-data.org's spelling so the live goal match
works directly ("United States", "Cape Verde Islands", "South Korea").
"""

PLAYER_BETS = [  # team top-scorer markets we're tracking
    ("Julio Enciso", "Paraguay"),
    ("Mohamed Toure", "Australia"),
    ("Franck Kessié", "Ivory Coast"),
    ("Hazem Mastouri", "Tunisia"),
    ("Ante Budimir", "Croatia"),
    ("Heung-min Son", "South Korea"),
    ("Ayoub El Kaabi", "Morocco"),
    ("Luis Suárez", "Colombia"),
    ("Ali Abdi", "Tunisia"),
    ("Breel Embolo", "Switzerland"),
    ("Eldor Shomurodov", "Uzbekistan"),
    ("Christian Pulisic", "United States"),
    ("Keito Nakamura", "Japan"),
    ("Amirhossein Hosseinzadeh", "Iran"),
    ("Matheus Cunha", "Brazil"),
    ("Nick Woltemade", "Germany"),
    ("No Scorer", "Ghana"),   # wins if no Ghana player scores; matches no real
                              # scorer, so D stays 0 and F tracks Ghana's top scorer
    ("Casemiro", "Brazil"),
    ("Bruno Guimarães", "Brazil"),
    ("Gabriel Magalhães", "Brazil"),
    ("Amadou Onana", "Belgium"),
    ("Rodri", "Spain"),
    ("Herrington", "Australia"),
    ("O'Neill", "Australia"),
    ("Josip Stanišić", "Croatia"),
    ("Dávinson Sánchez", "Colombia"),
    ("Aria Yousefi", "Iran"),
    ("Thomas Meunier", "Belgium"),
    ("Brandon Mechele", "Belgium"),
    ("Timothy Castagne", "Belgium"),
    ("Yazan Al-Arab", "Jordan"),
    ("Husam Abu Dahab", "Jordan"),
    ("Saed Al-Rosan", "Jordan"),
    ("Salim Obaid", "Jordan"),
    ("Mohammad Abu Hashish", "Jordan"),
    ("Abdallah Nasib", "Jordan"),
    ("Ihsan Haddad", "Jordan"),
    ("Nizar Al-Rashdan", "Jordan"),
    ("Rafik Belghali", "Algeria"),
    ("Ramy Bensebaini", "Algeria"),
    ("Aissa Mandi", "Algeria"),
    ("Rayan Ait-Nouri", "Algeria"),
    ("Ronald Araujo", "Uruguay"),
    ("Jose Maria Gimenez", "Uruguay"),
    ("Facundo Pellistri", "Uruguay"),
    ("Nicolas Tagliafico", "Argentina"),
    ("Roberto Lopes", "Cape Verde Islands"),
    ("Diney", "Cape Verde Islands"),
    ("Abdukodir Khusanov", "Uzbekistan"),
    ("Azizjon Ganiev", "Uzbekistan"),
    ("Shojae Khalilzadeh", "Iran"),
    ("Ramin Rezaeian", "Iran"),
    ("Ali Nemati", "Iran"),
    ("Tommy Smith", "New Zealand"),
    ("Callan Elliot", "New Zealand"),
    ("Andrew Robertson", "Scotland"),
    ("Emmanuel Agbadou", "Ivory Coast"),
    ("Ramon Sosa", "Paraguay"),
    ("Jefferson Lerma", "Colombia"),
]
