from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import requests
import os
from datetime import datetime
import pytz
import json

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

API_KEY = os.getenv("API_KEY")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_TOKEN = os.getenv("REDIS_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {REDIS_TOKEN}",
    "Content-Type": "application/json"
}

# Allowed sports keys to show
ALLOWED_SPORTS = [
    "tennis",
    "basketball_wnba",
    "basketball_nba",
    "americanfootball_ncaaf",
    "americanfootball_nfl",
    "mma_mixed_martial_arts"
]

MARKETS = ["h2h", "spreads", "totals"]

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

@app.route("/sports")
def sports():
    # Fetch sports from Odds API
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={API_KEY}"
    res = requests.get(url)
    if res.status_code != 200:
        print(f"[SPORTS API ERROR] {res.status_code} {res.text}")
        return jsonify({"error": "Failed to fetch sports"}), 500

    data = res.json()
    # Filter to only allowed sports
    filtered = [s for s in data if s["key"] in ALLOWED_SPORTS]
    return jsonify(filtered)

@app.route("/odds/<sport>")
def odds(sport):
    bookmaker = request.args.get("bookmaker", "betonlineag")
    if sport not in ALLOWED_SPORTS:
        return jsonify({"error": "Sport not supported"}), 400

    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        f"?regions=us&markets={','.join(MARKETS)}&bookmakers={bookmaker}&apiKey={API_KEY}"
    )
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

        # Prepare market data buckets
        moneyline = {}
        spread = {}
        total = {}

        for bm in game["bookmakers"]:
            if bm["key"] != bookmaker:
                continue

            for market in bm["markets"]:
                if market["key"] not in MARKETS:
                    continue

                for outcome in market["outcomes"]:
                    team = outcome["name"]
                    point = outcome.get("point")
                    live_decimal = outcome.get("price")

                    key_prefix = sport + ":" + game['id'] + ":" + market["key"] + ":" + team + ":open"
                    open_decimal_raw = get_opening_line(key_prefix)
                    open_decimal = None
                    if open_decimal_raw:
                        try:
                            open_decimal = json.loads(open_decimal_raw).get("value")
                        except Exception as e:
                            print("Error parsing open_decimal JSON:", e)
                            open_decimal = None

                    if not open_decimal and live_decimal is not None:
                        save_opening_line(key_prefix, live_decimal)
                        open_decimal = live_decimal

                    diff = "+0"
                    if open_decimal is not None and live_decimal is not None:
                        if market["key"] == "spreads" or market["key"] == "totals":
                            try:
                                diff_val = float(point) - float(json.loads(open_decimal_raw).get("value")) if open_decimal_raw else 0
                                diff = f"{diff_val:+.1f}"
                            except:
                                diff = "+0"
                        else:
                            try:
                                diff_val = int((float(live_decimal) - float(open_decimal)) * 100)
                                diff = f"{diff_val:+}"
                            except:
                                diff = "+0"

                    # Build proper dict per market
                    display_open = (
                        f"{point} ({to_american(open_decimal)})"
                        if market["key"] in ["spreads", "totals"] and point is not None
                        else to_american(open_decimal)
                    )
                    display_live = (
                        f"{point} ({to_american(live_decimal)})"
                        if market["key"] in ["spreads", "totals"] and point is not None
                        else to_american(live_decimal)
                    )

                    market_dict = {
                        "open": display_open,
                        "live": display_live,
                        "diff": diff,
                    }

                    if market["key"] == "h2h":
                        moneyline[team] = market_dict
                    elif market["key"] == "spreads":
                        spread[team] = market_dict
                    elif market["key"] == "totals":
                        total[team] = market_dict

        results.append({
            "matchup": matchup,
            "commence_time": kickoff,
            "moneyline": moneyline,
            "spread": spread,
            "total": total
        })

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True, port=5050)
