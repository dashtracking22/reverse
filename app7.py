import os
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests, json, pytz, redis
from datetime import datetime

app = Flask(__name__, template_folder="templates", static_folder="static")

Talisman(app, force_https=False)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])
limiter.init_app(app)

CORS(app, origins=[
    "https://reversetracking.onrender.com",
    "https://www.yourdomain.com"
])

API_KEY           = os.getenv("THE_ODDS_API_KEY")
DEFAULT_BOOKMAKER = "draftkings"
MARKETS           = ["h2h", "spreads", "totals"]

BOOKMAKERS = [
    {"key": "betonlineag", "title": "BetOnlineAg"},
    {"key": "draftkings",  "title": "DraftKings"},
    {"key": "fan-duel",    "title": "FanDuel"}
]

SPORTS = [
    {"key": "baseball_mlb",           "title": "MLB"},
    {"key": "mma_mixed_martial_arts", "title": "MMA"},
    {"key": "basketball_wnba",        "title": "WNBA"},
    {"key": "americanfootball_nfl",   "title": "NFL"},
    {"key": "americanfootball_ncaaf", "title": "NCAAF"}
]

# Redis setup using Render environment variables
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD'),
    ssl=True
)

def decimal_to_american(d):
    if d >= 2.0:
        return f"+{round((d - 1) * 100)}"
    return f"-{round(100 / (d - 1))}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/bookmakers")
def get_bookmakers():
    return jsonify(BOOKMAKERS)

@app.route("/sports")
def get_sports():
    return jsonify(SPORTS)

@app.route("/odds/<sport>")
def get_odds(sport):
    if not API_KEY:
        return jsonify({"error": "Missing THE_ODDS_API_KEY"}), 500

    bookmaker = request.args.get("bookmaker", DEFAULT_BOOKMAKER)

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
            if not home or not away:
                continue
            matchup = f"{home} vs {away}"

            dt = datetime.strptime(game["commence_time"], "%Y-%m-%dT%H:%M:%SZ")
            kickoff = dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("US/Eastern"))
            kickoff_str = kickoff.strftime("%m/%d %I:%M %p")

            redis_key = f"opening_odds:{sport}:{matchup}"
            stored_data = redis_client.get(redis_key)

            all_markets = {}
            bk_data = next((b for b in game.get("bookmakers", []) if b["key"] == bookmaker), None)
            if not bk_data:
                continue

            current_odds = {}
            for m in bk_data.get("markets", []):
                key = m["key"]
                name = ("moneyline" if key == "h2h"
                        else "spread" if key == "spreads"
                        else "total" if key == "totals"
                        else None)
                if not name:
                    continue

                curr_price = {o["name"]: decimal_to_american(o["price"])
                              for o in m.get("outcomes", []) if o.get("price")}
                curr_point = {o["name"]: o["point"]
                              for o in m.get("outcomes", []) if o.get("point")}

                current_odds[name] = {"price": curr_price, "points": curr_point}

            if stored_data:
                opening_odds = json.loads(stored_data)
            else:
                opening_odds = current_odds
                redis_client.set(redis_key, json.dumps(opening_odds))

            diffs = {}
            for market in current_odds:
                diffs[market] = {}
                for team in current_odds[market]["price"]:
                    if market == "moneyline":
                        diffs[market][team] = int(current_odds[market]["price"][team]) - int(opening_odds[market]["price"][team])
                    else:
                        diffs[market][team] = round(current_odds[market]["points"][team] - opening_odds[market]["points"][team], 1)

                all_markets[market] = {
                    "opening": opening_odds[market],
                    "current": current_odds[market],
                    "diff": diffs[market]
                }

            results.append({
                "matchup": matchup,
                "commence_time_est": kickoff_str,
                "moneyline": all_markets.get("moneyline", {}),
                "spread": all_markets.get("spread", {}),
                "total": all_markets.get("total", {})
            })

        return jsonify(results)

    except Exception as e:
        print(f"❌ Error fetching odds for {sport}@{bookmaker}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
