import requests

API_KEY = "e9cb3bfd5865b71161c903d24911b88d"
BOOKMAKER = "betonlineag"
SPORTS = [
    "baseball_mlb",
    "mma_mixed_martial_arts",
    "basketball_wnba",
    "basketball_nba",
    "americanfootball_nfl",
    "americanfootball_ncaaf"
]

for sport in SPORTS:
    print(f"\n🎯 Checking {sport}...")
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?regions=us&markets=h2h&bookmakers={BOOKMAKER}&apiKey={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data:
            print(f"✅ SUCCESS: Got {len(data)} games")
        else:
            print(f"⚠️ No games found for {sport}")
    except Exception as e:
        print(f"❌ ERROR for {sport}: {e}")
