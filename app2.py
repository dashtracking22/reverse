from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import os
import json

app = Flask(__name__)
CORS(app)

API_KEY = "e9cb3bfd5865b71161c903d24911b88d"
BOOKMAKER = "betonlineag"
SPORTS = [
    {"key": "baseball_mlb", "title": "MLB"},
    {"key": "mma_mixed_martial_arts", "title": "MMA"},
    {"key": "basketball_wnba", "title": "WNBA"},
    {"key": "americanfootball_nfl", "title": "NFL"},
    {"key": "americanfootball_ncaaf", "title": "NCAAF"}
]

ODDS_LOG_FILE = "odds_log.json"

# Load previously saved opening odds
def load_odds_log():
    if os.path.exists(ODDS_LOG_FILE):
        with open(ODDS_LOG_FILE, "r") as f:
            return json.load(f)
    return {}

# Save updated odds to file
def save_odds_log(log):
    with open(ODDS_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

@app.route("/")
def index():
    return render_template("BETTRACKER2.html")

@app.route("/sports")
def get_sports():
    return jsonify(SPORTS)

@app.route("/odds/<sport>")
def get_odds(sport):
    odds_log = load_odds_log()

    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?regions=us&markets=h2h&bookmakers={BOOKMAKER}&apiKey={API_KEY}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        results = []

        for game in data:
            home = game.get("home_team")
            away = game.get("away_team")
            matchup = f"{home} vs {away}"

            try:
                outcomes = game["bookmakers"][0]["markets"][0]["outcomes"]
            except (IndexError, KeyError):
                continue

            current = {o["name"]: o["price"] for o in outcomes}

            if sport not in odds_log:
                odds_log[sport] = {}

            if matchup not in odds_log[sport]:
                odds_log[sport][matchup] = current

            opening = odds_log[sport][matchup]

            movement = {}
            for team in current:
                if team in opening:
                    movement[team] = round(current[team] - opening[team], 2)

            results.append({
                "matchup": matchup,
                "opening": opening,
                "current": current,
                "movement": movement
            })

        save_odds_log(odds_log)
        return jsonify(results)

    except Exception as e:
        print(f"❌ Error fetching odds for {sport}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5050)
