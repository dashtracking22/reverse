from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

API_KEY = "e9cb3bfd5865b71161c903d24911b88d"
BOOKMAKER = "betonlineag"
MARKETS = ["h2h", "spreads", "totals"]
ODDS_LOG_FILE = "odds_log.json"

SPORTS = [
    {"key": "baseball_mlb", "title": "MLB"},
    {"key": "mma_mixed_martial_arts", "title": "MMA"},
    {"key": "basketball_wnba", "title": "WNBA"},
    {"key": "americanfootball_nfl", "title": "NFL"},
    {"key": "americanfootball_ncaaf", "title": "NCAAF"}
]

def load_odds_log():
    if os.path.exists(ODDS_LOG_FILE):
        with open(ODDS_LOG_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_odds_log(log):
    with open(ODDS_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

def decimal_to_american(d):
    if d >= 2.0:
        return f"+{round((d - 1) * 100)}"
    else:
        return f"-{round(100 / (d - 1))}"

@app.route("/")
def index():
    return render_template("betkarma3.html")

@app.route("/sports")
def get_sports():
    return jsonify(SPORTS)

@app.route("/odds/<sport>")
def get_odds(sport):
    odds_log = load_odds_log()
    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        f"?regions=us&markets={','.join(MARKETS)}"
        f"&bookmakers={BOOKMAKER}&apiKey={API_KEY}"
    )
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        results = []

        for game in data:
            home = game.get("home_team")
            away = game.get("away_team")
            if not home or not away:
                continue
            matchup = f"{home} vs {away}"

            # Format kickoff EST
            raw = game.get("commence_time")
            dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
            est = pytz.timezone("US/Eastern")
            kickoff = dt.replace(tzinfo=pytz.utc).astimezone(est)
            kickoff_str = kickoff.strftime("%m/%d %I:%M %p")

            # Ensure log structure
            odds_log.setdefault(sport, {})
            odds_log[sport].setdefault(matchup, {})

            all_markets = {}
            bm = game.get("bookmakers", [])
            if not bm:
                continue
            for m in bm[0].get("markets", []):
                key = m["key"]
                name = (
                    "moneyline" if key == "h2h" else
                    "spread"    if key == "spreads" else
                    "total"     if key == "totals" else
                    None
                )
                if not name:
                    continue

                # Gather current prices & points
                curr_price = {}
                curr_point = {}
                for o in m.get("outcomes", []):
                    team = o["name"]
                    price = o.get("price")
                    point = o.get("point")
                    if team and price is not None:
                        curr_price[team] = decimal_to_american(price)
                    if team and point is not None:
                        curr_point[team] = point

                # Save opening if first time
                if name not in odds_log[sport][matchup]:
                    odds_log[sport][matchup][name] = {
                        "price": curr_price.copy(),
                        "points": curr_point.copy()
                    }

                opening = odds_log[sport][matchup][name]
                open_price  = opening.get("price", {})
                open_points = opening.get("points", {})

                # Compute diffs
                diffs = {}
                for team in curr_price:
                    if name == "moneyline" and team in open_price:
                        cv = int(curr_price[team])
                        ov = int(open_price[team])
                        diffs[team] = cv - ov
                    elif name in ("spread", "total") and team in curr_point and team in open_points:
                        diffs[team] = round(curr_point[team] - open_points[team], 1)

                all_markets[name] = {
                    "opening": {"price": open_price,  "points": open_points},
                    "current": {"price": curr_price,   "points": curr_point},
                    "diff":    diffs
                }

            results.append({
                "matchup": matchup,
                "commence_time_est": kickoff_str,
                "moneyline": all_markets.get("moneyline", {}),
                "spread":    all_markets.get("spread",    {}),
                "total":     all_markets.get("total",     {})
            })

        save_odds_log(odds_log)
        return jsonify(results)

    except Exception as e:
        print(f"❌ Error fetching odds for {sport}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5050)
