from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime
from pytz import timezone

app = Flask(__name__)
CORS(app)

API_KEY = "YOUR_REAL_ODDS_API_KEY"  # Replace with your actual Odds API key
BASE_URL = "https://api.the-odds-api.com/v4/sports"

SUPPORTED_SPORTS = [
    "baseball_mlb",
    "mma_mixed_martial_arts",
    "basketball_wnba",
    "americanfootball_nfl",
    "americanfootball_ncaaf"
]

BOOKMAKER_MAP = {
    "betonlineag": "betonlineag",
    "draftkings": "draftkings",
    "fan-duel": "fanduel"
}

MARKETS = ["h2h", "spreads", "totals"]

LOG_FILE = "odds_log.json"

# Safely read or initialize odds log
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w") as f:
        json.dump({}, f)

try:
    with open(LOG_FILE, "r") as f:
        odds_log = json.load(f)
except json.JSONDecodeError:
    odds_log = {}
    with open(LOG_FILE, "w") as f:
        json.dump(odds_log, f)

def save_log():
    with open(LOG_FILE, "w") as f:
        json.dump(odds_log, f, indent=2)

def convert_to_est(utc_str):
    est = timezone("US/Eastern")
    dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ")
    return dt.astimezone(est).strftime("%m/%d %I:%M %p")

def fetch_odds(sport, bookmaker):
    url = f"{BASE_URL}/{sport}/odds/?regions=us&markets={','.join(MARKETS)}&bookmakers={bookmaker}&apiKey={API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    return response.json()

def format_game(game, bookmaker):
    est_time = convert_to_est(game["commence_time"])
    teams = game["teams"]
    home_team = game["home_team"]
    away_team = [t for t in teams if t != home_team][0]

    def extract_market_data(key, market):
        outcomes = next((m for m in game["bookmakers"][0]["markets"] if m["key"] == key), {}).get("outcomes", [])
        data = {}
        for outcome in outcomes:
            name = outcome.get("name")
            price = outcome.get("price")
            point = outcome.get("point")
            if name:
                data[name] = {"price": price, "point": point}
        return data

    h2h = extract_market_data("h2h", game)
    spreads = extract_market_data("spreads", game)
    totals = extract_market_data("totals", game)

    game_key = game["id"]
    if game_key not in odds_log:
        odds_log[game_key] = {
            "h2h": h2h,
            "spreads": spreads,
            "totals": totals
        }
        save_log()

    open_data = odds_log[game_key]

    def get_diff(current, original, is_point=False):
        diffs = {}
        for team in current:
            if team in original:
                val1 = current[team].get("point" if is_point else "price")
                val0 = original[team].get("point" if is_point else "price")
                if val1 is not None and val0 is not None:
                    try:
                        diffs[team] = round(val1 - val0, 1 if is_point else 0)
                    except:
                        diffs[team] = 0
        return diffs

    return {
        "matchup": f"{away_team} vs {home_team}",
        "time": est_time,
        "moneyline": {
            "open": open_data["h2h"],
            "live": h2h,
            "diff": get_diff(h2h, open_data["h2h"])
        },
        "spread": {
            "open": open_data["spreads"],
            "live": spreads,
            "diff": get_diff(spreads, open_data["spreads"], is_point=True)
        },
        "total": {
            "open": open_data["totals"],
            "live": totals,
            "diff": get_diff(totals, open_data["totals"], is_point=True)
        }
    }

@app.route("/sports")
def get_sports():
    return jsonify(SUPPORTED_SPORTS)

@app.route("/odds/<sport>")
def get_odds(sport):
    bookmaker = request.args.get("bookmaker", "betonlineag")
    if sport not in SUPPORTED_SPORTS or bookmaker not in BOOKMAKER_MAP:
        return jsonify([])
    odds_data = fetch_odds(sport, BOOKMAKER_MAP[bookmaker])
    formatted = [format_game(game, bookmaker) for game in odds_data if "bookmakers" in game and game["bookmakers"]]
    return jsonify(formatted)

if __name__ == "__main__":
    app.run(debug=True, port=5050)
