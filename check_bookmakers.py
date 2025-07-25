import requests

API_KEY = "e9cb3bfd5865b71161c903d24911b88d"
sports_to_test = [
    "basketball_wnba",
    "basketball_nba",
    "mma_ufc",              # UFC replaces "mma_mixed_martial_arts"
    "baseball_mlb",
]

for sport in sports_to_test:
    print(f"\n🎯 Checking bookmakers for {sport}...")
    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        f"?regions=us&markets=moneyline&apiKey={API_KEY}"
    )
    try:
        response = requests.get(url)
        response.raise_for_status()
        games = response.json()

        if not games:
            print("❌ No games found.")
            continue

        bks = set()
        for game in games:
            for book in game.get("bookmakers", []):
                bks.add(book["key"])
        print("✅ Found these bookmakers:", ", ".join(sorted(bks)))
    except Exception as e:
        print("⚠️ Error:", e)