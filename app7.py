from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests
import redis
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=int(REDIS_PORT),
    password=REDIS_PASSWORD,
    ssl=True,
    decode_responses=True
)

THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY")
BOOKMAKER = "betonlineag"
MARKETS = ["h2h", "spreads", "totals"]

@app.route("/odds/<sport>")
def get_odds(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        "regions": "us",
        "markets": ",".join(MARKETS),
        "bookmakers": BOOKMAKER,
        "apiKey": THE_ODDS_API_KEY
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return jsonify({"error": f"API failed: {response.status_code}"}), 500

    games = response.json()
    result = []

    for game in games:
        game_data = {
            "matchup": f"{game['home_team']} vs {game['away_team']}",
            "commence_time": game["commence_time"],
            "moneyline": {},
            "spread": {},
            "total": {}
        }

        key = f"opening_odds:{sport}:{game_data['matchup']}"
        if not redis_client.exists(key):
            opening_data = {"moneyline": {}, "spread": {}, "total": {}}
            for market in game.get("bookmakers", [])[0].get("markets", []):
                if market["key"] == "h2h":
                    for outcome in market["outcomes"]:
                        opening_data["moneyline"][outcome["name"]] = outcome["price"]
                elif market["key"] == "spreads":
                    for outcome in market["outcomes"]:
                        opening_data["spread"][outcome["name"]] = {
                            "point": outcome["point"], "price": outcome["price"]
                        }
                elif market["key"] == "totals":
                    for outcome in market["outcomes"]:
                        opening_data["total"][outcome["name"]] = {
                            "point": outcome["point"], "price": outcome["price"]
                        }
            redis_client.set(key, str(opening_data))
        else:
            opening_data = eval(redis_client.get(key))

        for market in game.get("bookmakers", [])[0].get("markets", []):
            if market["key"] == "h2h":
                for outcome in market["outcomes"]:
                    name = outcome["name"]
                    current = outcome["price"]
                    opening = opening_data["moneyline"].get(name, current)
                    diff = current - opening
                    game_data["moneyline"][name] = {
                        "open": opening, "live": current, "diff": diff
                    }

            elif market["key"] == "spreads":
                for outcome in market["outcomes"]:
                    name = outcome["name"]
                    current_point = outcome["point"]
                    current_price = outcome["price"]
                    opening = opening_data["spread"].get(name, {"point": current_point})
                    diff = round(current_point - opening["point"], 1)
                    game_data["spread"][name] = {
                        "open": opening["point"], "live": current_point, "diff": diff,
                        "open_price": opening.get("price"), "live_price": current_price
                    }

            elif market["key"] == "totals":
                for outcome in market["outcomes"]:
                    name = outcome["name"]
                    current_point = outcome["point"]
                    current_price = outcome["price"]
                    opening = opening_data["total"].get(name, {"point": current_point})
                    diff = round(current_point - opening["point"], 1)
                    game_data["total"][name] = {
                        "open": opening["point"], "live": current_point, "diff": diff,
                        "open_price": opening.get("price"), "live_price": current_price
                    }

        result.append(game_data)

    return jsonify(result)

@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

if __name__ == "__main__":
    app.run(port=5050)
