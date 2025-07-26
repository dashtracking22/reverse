from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import os
from datetime import datetime
import pytz
import json

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Load environment variables
API_KEY = os.getenv("API_KEY")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_TOKEN = os.getenv("REDIS_TOKEN")

# Sport & bookmaker
SPORT = "mma_mixed_martial_arts"
BOOKMAKER = "draftkings"
MARKET = "h2h"

HEADERS = {
    "Authorization": f"Bearer {REDIS_TOKEN}",
    "Content-Type": "application/json"
}

def save_opening_line(key, value):
    url = f"{REDIS_URL}/set/{key}"
    payload = json.dumps({"value": value})
    try:
        res = requests.post(url, headers=HEADERS, data=payload)
        print(f"[Redis SET] {key} = {value} → {res.status_code}")
    except Exception as e:
        print("[Redis save error]", e)

def get_opening_line(key):
    url = f"{REDIS_URL}/get/{key}"
    try:
        res = requests.get(url, headers=HEADERS)
        print(f"[Redis GET] {key} → {res.status_code}: {res.text}")
        if res.status_code == 200 and res.json().get("result"):
            return res.json()["result"]
    except Exception as e:
        print("[Redis get error]", e)
    return None

def to_american(decimal):
    try:
        decimal = float(decimal)
        if decimal >= 2:
            return f"+{int((decimal - 1) * 100)}"
        elif decimal > 1:
            return f"-{int(100 / (decimal - 1))}"
    except:
        pass
    return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/odds")
def odds():
    print("🔑 Loaded API_KEY:", API_KEY)
    print("🔑 REDIS_URL:", REDIS_URL)
    print("🔑 REDIS_TOKEN:", REDIS_TOKEN[:10] + "..." if REDIS_TOKEN else "None")

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/?regions=us&markets={MARKET}&bookmakers={BOOKMAKER}&apiKey={API_KEY}"
    print("[Odds API Request]:", url)
    res = requests.get(url)

    if res.status_code != 200:
        print("[ODDS API ERROR]:", res.status_code, res.text)
        return jsonify({"error": "Failed to fetch odds", "details": res.text}), 500

    try:
        data = res.json()
    except Exception as e:
        print("[JSON parse error]:", e)
        return jsonify({"error": "Invalid JSON response"}), 500

    eastern = pytz.timezone("US/Eastern")
    results = []

    for game in data:
        matchup = f"{game['home_team']} vs {game['away_team']}"
        start_time = datetime.fromisoformat(game['commence_time'].replace("Z", "+00:00")).astimezone(eastern)
        kickoff = start_time.strftime("%m/%d, %I:%M %p ET")

        game_odds = {}

        for bm in game["bookmakers"]:
            if bm["key"] != BOOKMAKER:
                continue

            for market in bm["markets"]:
                if market["key"] != MARKET:
                    continue

                for outcome in market["outcomes"]:
                    team = outcome["name"]
                    live_decimal = outcome.get("price")
                    open_key = f"{SPORT}:{game['id']}:moneyline:{team}:open"

                    open_decimal = get_opening_line(open_key)
                    if not open_decimal and live_decimal:
                        save_opening_line(open_key, live_decimal)
                        open_decimal = live_decimal

                    diff = (
                        f"{int((float(live_decimal) - float(open_decimal)) * 100):+}"
                        if open_decimal and live_decimal else "+0"
                    )

                    game_odds[team] = {
                        "open": to_american(open_decimal),
                        "live": to_american(live_decimal),
                        "diff": diff
                    }

        results.append({
            "matchup": matchup,
            "commence_time": kickoff,
            "moneyline": game_odds
        })

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True, port=5050)
