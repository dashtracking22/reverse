# app3.py
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import requests, os, json
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

API_KEY        = "e9cb3bfd5865b71161c903d24911b88d"
MARKETS        = ["h2h", "spreads", "totals"]
ODDS_LOG_FILE  = "odds_log.json"

# Default and available bookmakers
DEFAULT_BOOKMAKER = "bdraftkings"
BOOKMAKERS = [
    {"key": "betonlineag",       "title": "BetOnlineAg"},
    {"key": "draftkings",        "title": "DraftKings"},
    {"key": "fan-duel",          "title": "FanDuel"}
]

SPORTS = [
    {"key": "baseball_mlb",            "title": "MLB"},
    {"key": "mma_mixed_martial_arts",  "title": "MMA"},
    {"key": "basketball_wnba",         "title": "WNBA"},
    {"key": "americanfootball_nfl",    "title": "NFL"},
    {"key": "americanfootball_ncaaf",  "title": "NCAAF"}
]

def load_odds_log():
    if os.path.exists(ODDS_LOG_FILE):
        try:
            return json.load(open(ODDS_LOG_FILE))
        except json.JSONDecodeError:
            return {}
    return {}

def save_odds_log(log):
    with open(ODDS_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

def decimal_to_american(d):
    if d >= 2.0:
        return f"+{round((d - 1) * 100)}"
    return f"-{round(100 / (d - 1))}"

@app.route("/")
def index():
    return render_template("betkarma4.html")

@app.route("/bookmakers")
def get_bookmakers():
    return jsonify(BOOKMAKERS)

@app.route("/sports")
def get_sports():
    return jsonify(SPORTS)

@app.route("/odds/<sport>")
def get_odds(sport):
    # pick user-selected or default bookmaker
    bookmaker = request.args.get("bookmaker", DEFAULT_BOOKMAKER)
    odds_log  = load_odds_log()

    url = (
      f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
      f"?regions=us&markets={','.join(MARKETS)}"
      f"&bookmakers={bookmaker}&apiKey={API_KEY}"
    )

    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        results = []

        for game in data:
            home, away = game.get("home_team"), game.get("away_team")
            if not home or not away: continue
            matchup = f"{home} vs {away}"

            # convert kickoff to EST
            dt = datetime.strptime(game["commence_time"], "%Y-%m-%dT%H:%M:%SZ")
            kickoff = dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("US/Eastern"))
            kickoff_str = kickoff.strftime("%m/%d %I:%M %p")

            # prepare log
            odds_log.setdefault(sport, {}).setdefault(matchup, {})

            all_markets = {}
            bk_list = game.get("bookmakers", [])
            # find the chosen bookmaker entry
            bk_data = next((b for b in bk_list if b["key"] == bookmaker), None)
            if not bk_data: continue

            for m in bk_data.get("markets", []):
                name = ("moneyline" if m["key"] == "h2h"
                        else "spread" if m["key"] == "spreads"
                        else "total"  if m["key"] == "totals"
                        else None)
                if not name: continue

                curr_price = {o["name"]: decimal_to_american(o["price"])
                              for o in m["outcomes"] if o.get("price") is not None}
                curr_point = {o["name"]: o["point"]
                              for o in m["outcomes"] if o.get("point") is not None}

                # save opening if first time
                log_entry = odds_log[sport][matchup].setdefault(name, {
                  "price": {}, "points": {}
                })
                if not log_entry["price"]:
                    log_entry["price"].update(curr_price)
                    log_entry["points"].update(curr_point)

                opening_price  = log_entry["price"]
                opening_points = log_entry["points"]

                # compute diffs
                diffs = {}
                for team in curr_price:
                    if name == "moneyline" and team in opening_price:
                        diffs[team] = int(curr_price[team]) - int(opening_price[team])
                    elif name in ("spread","total") and team in opening_points:
                        diffs[team] = round(curr_point[team] - opening_points[team], 1)

                all_markets[name] = {
                  "opening": {"price": opening_price, "points": opening_points},
                  "current": {"price": curr_price,    "points": curr_point},
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
        print(f"❌ Error fetching odds for {sport}@{bookmaker}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5050)
