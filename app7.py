from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import os
import pytz
from datetime import datetime
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

MARKETS = ["h2h", "spreads", "totals"]
BOOKMAKER = "betonlineag"

def save_opening_line(key, value):
    url = f"{REDIS_URL}/set/{key}"
    payload = json.dumps({"value": value})
    requests.post(url, headers=HEADERS, data=payload)

def get_opening_line(key):
    url = f"{REDIS_URL}/get/{key}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200 and res.json().get("result"):
        return res.json()["result"]
    return None

def to_american(decimal):
    if decimal is None or decimal == 0: return None
    try:
        decimal = float(decimal)
        if decimal >= 2:
            return f"+{int((decimal - 1) * 100)}"
        else:
            return f"-{int(100 / (decimal - 1))}"
    except:
        return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sports")
def sports():
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={API_KEY}"
    res = requests.get(url)
    data = res.json()
    valid_keys = [
        "baseball_mlb",
        "mma_mixed_martial_arts",
        "basketball_wnba",
        "americanfootball_nfl",
        "americanfootball_ncaaf"
    ]
    return jsonify([s for s in data if s["key"] in valid_keys])

@app.route("/odds/<sport>")
def odds(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?regions=us&markets={','.join(MARKETS)}&bookmakers={BOOKMAKER}&apiKey={API_KEY}"
    res = requests.get(url)
    if res.status_code != 200:
        return jsonify({"error": "Failed to fetch odds"}), 500

    data = res.json()
    eastern = pytz.timezone("US/Eastern")
    games = []

    for game in data:
        matchup = f"{game['home_team']} vs {game['away_team']}"
        commence_time = datetime.fromisoformat(game['commence_time'].replace("Z", "+00:00")).astimezone(eastern)
        kickoff = commence_time.strftime("%m/%d, %I:%M %p ET")

        game_data = {
            "matchup": matchup,
            "commence_time": kickoff,
            "moneyline": {},
            "spread": {},
            "total": {}
        }

        for bm in game["bookmakers"]:
            if bm["key"] != BOOKMAKER:
                continue

            for market in bm["markets"]:
                label = market["key"]

                for outcome in market["outcomes"]:
                    team = outcome.get("name")
                    decimal = outcome.get("price")
                    point = outcome.get("point")

                    if label == "h2h":
                        key = f"{sport}:{game['id']}:moneyline:{team}:open"
                        open_val = get_opening_line(key)
                        if not open_val and decimal:
                            save_opening_line(key, decimal)
                            open_val = decimal
                        diff = f"{int((float(decimal) - float(open_val)) * 100):+}" if open_val else "+0"

                        game_data["moneyline"][team] = {
                            "open": to_american(open_val),
                            "live": to_american(decimal),
                            "diff": diff
                        }

                    elif label == "spreads":
                        key = f"{sport}:{game['id']}:spread:{team}:open"
                        open_val = get_opening_line(key)
                        if not open_val and point is not None:
                            save_opening_line(key, point)
                            open_val = point
                        diff = round(float(point) - float(open_val), 1) if open_val else 0

                        game_data["spread"][team] = {
                            "open": f"{open_val} ({to_american(decimal)})",
                            "live": f"{point} ({to_american(decimal)})",
                            "diff": f"{diff:+.1f}"
                        }

                    elif label == "totals":
                        key = f"{sport}:{game['id']}:total:{team}:open"
                        open_val = get_opening_line(key)
                        if not open_val and point is not None:
                            save_opening_line(key, point)
                            open_val = point
                        diff = round(float(point) - float(open_val), 1) if open_val else 0

                        game_data["total"][team] = {
                            "open": f"{open_val} ({to_american(decimal)})",
                            "live": f"{point} ({to_american(decimal)})",
                            "diff": f"{diff:+.1f}"
                        }

        games.append(game_data)

    return jsonify(games)

if __name__ == "__main__":
    app.run(debug=True, port=5050)
