# check_sports_live.py
import requests

API_KEY = "e9cb3bfd5865b71161c903d24911b88d"
BOOKMAKER = "betonlineag"
SPORTS = [
    "basketball_nba", "basketball_wnba", "baseball_mlb",
    "mma_mixed_martial_arts", "mma_ufc", "americanfootball_nfl"
]

for sport in SPORTS:
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?regions=us&markets=h2h&bookmakers={BOOKMAKER}&apiKey={API_KEY}"
    print(f"\n🎯 Checking odds for {sport}...")
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        if data:
            print(f"✅ Odds found: {len(data)} games")
        else:
            print("❌ No odds currently available")
    except Exception as e:
        print(f"❌ Error: {e}")
