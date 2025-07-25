import time
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

CACHE_DURATION = 30  # seconds
_cache = {}

ALLOWED_SPORTS = [
    "tennis",
    "basketball_wnba",
    "basketball_nba",
    "americanfootball_ncaaf",
    "americanfootball_nfl",
    "mma_mixed_martial_arts"
]

MARKETS = ["h2h", "spreads", "totals"]


def get_redis_credentials():
    base_url = os.getenv("REDIS_URL")
    port = os.getenv("REDIS_PORT")
    token = os.getenv("REDIS_TOKEN")
    if base_url and port:
        redis_url = f"{base_url}:{port}"
    else:
        redis_url = base_url  # fallback if port missing
    return redis_url, token


def save_opening_line(redis_url, headers, key, value):
    url = f"{redis_url}/set/{key}"
    payload = json.dumps({"value": value})
    try:
        res = requests.post(url, headers=headers, data=payload)
        print(f"[Redis SET] {key} = {value} → {res.status_code}")
    except Exception as e:
        print("[Redis save error]", e)


def batch_get_opening_lines(redis_url, headers, keys):
    url = f"{redis_url}/mget"
    try:
        payload = json.dumps(keys)
        res = requests.post(url, headers=headers, data=payload)
        if res.status_code == 200:
            return res.json().get("result", [])
    except Exception as e:
        print("[Redis batch get error]", e)
    return [None] * len(keys)


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


def get_sports_cached():
    now = time.time()
    if "sports" in _cache and now - _cache["sports"]["time"] < CACHE_DURATION:
        return _cache["sports"]["data"]

    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={API_KEY}"
    res = requests.get(url)
    if res.status_code == 200:
        _cache["sports"] = {"time": now, "data": res.json()}
        return _cache["sports"]["data"]
    return []


def get_odds_cached(sport, bookmaker, markets):
    now = time.time()
    key = f"odds_{sport}_{bookmaker}"
    if key in _cache and now - _cache[key]["time"] < CACHE_DURATION:
        return _cache[key]["data"]

    url = (
        f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        f"?regions=us&markets={','.join(markets)}&bookmakers={bookmaker}&apiKey={API_KEY}"
    )
    res = requests.get(url)
    if res.status_code == 200:
        _cache[key] = {"time": now, "data": res.json()}
        return _cache[key]["data"]
    else:
        print(f"[ODDS API ERROR] {res.status_code} {res.text}")
        return None


### Redis test helpers ###

redis_url, redis_token = get_redis_credentials()
redis_headers = {
    "Authorization": f"Bearer {redis_token}",
    "Content-Type": "application/json"
}


def redis_set(key, value):
    url = f"{redis_url}/set/{key}"
    payload = json.dumps({"value": value})
    try:
        res = requests.post(url, headers=redis_headers, data=payload)
        return res.status_code, res.text
    except Exception as e:
        return 500, str(e)


def redis_get(key):
    url = f"{redis_url}/get/{key}"
    try:
        res = requests.get(url, headers=redis_headers)
        return res.status_code, res.text
    except Exception as e:
        return 500, str(e)


@app.route("/test_redis")
def test_redis():
    test_key = "test_key"
    test_value = "hello from redis"
    
    set_status, set_resp = redis_set(test_key, test_value)
    get_status, get_resp = redis_get(test_key)
    
    return jsonify({
        "set_status": set_status,
        "set_response": set_resp,
        "get_status": get_status,
        "get_response": get_resp,
    })


@app.route("/")
def home():
    return "BetKarma Redis Test App is running."


@app.route("/sports")
def sports():
    data = get_sports_cached()
    filtered = [s for s in data if s["key"] in ALLOWED_SPORTS]
    return jsonify(filtered)


@app.route("/odds/<sport>")
def odds(sport):
    bookmaker = request.args.get("bookmaker", "betonlineag")

    if sport not in ALLOWED_SPORTS:
        return jsonify({"error": "Sport not supported"}), 400

    if not redis_url or not redis_token:
        return jsonify({"error": "Redis credentials not configured properly"}), 500

    data = get_odds_cached(sport, bookmaker, MARKETS)
    if data is None:
        return jsonify({"error": "Failed to fetch odds"}), 500

    eastern = pytz.timezone("US/Eastern")
    results = []

    redis_keys = []
    key_to_info = {}

    for game in data:
        for bm in game["bookmakers"]:
            if bm["key"] != bookmaker:
                continue
            for market in bm["markets"]:
                if market["key"] not in MARKETS:
                    continue
                for outcome in market["outcomes"]:
                    team = outcome["name"]
                    key_odds = f"{sport}:{game['id']}:{market['key']}:{team}:open_odds"
                    key_point = f"{sport}:{game['id']}:{market['key']}:{team}:open_point"
                    redis_keys.append(key_odds)
                    redis_keys.append(key_point)
                    key_to_info[key_odds] = (game, bm, market, outcome)
                    key_to_info[key_point] = (game, bm, market, outcome)

    redis_results = batch_get_opening_lines(redis_url, redis_headers, redis_keys)
    redis_values = dict(zip(redis_keys, redis_results))

    for game in data:
        matchup = f"{game['home_team']} vs {game['away_team']}"
        start_time = datetime.fromisoformat(game['commence_time'].replace("Z", "+00:00")).astimezone(eastern)
        kickoff = start_time.strftime("%m/%d, %I:%M %p ET")

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

                    odds_key = f"{sport}:{game['id']}:{market['key']}:{team}:open_odds"
                    point_key = f"{sport}:{game['id']}:{market['key']}:{team}:open_point"

                    open_odds_raw = redis_values.get(odds_key)
                    open_point_raw = redis_values.get(point_key)

                    open_odds = None
                    open_point = None

                    if open_odds_raw:
                        try:
                            open_odds = float(json.loads(open_odds_raw).get("value"))
                        except Exception:
                            pass

                    if open_point_raw:
                        try:
                            open_point = float(json.loads(open_point_raw).get("value"))
                        except Exception:
                            pass

                    if open_odds is None and live_decimal is not None:
                        save_opening_line(redis_url, redis_headers, odds_key, live_decimal)
                        open_odds = live_decimal

                    if open_point is None and point is not None:
                        save_opening_line(redis_url, redis_headers, point_key, point)
                        open_point = point

                    diff = "+0"

                    if market["key"] in ["spreads", "totals"]:
                        if open_point is not None and point is not None:
                            try:
                                diff_val = float(point) - float(open_point)
                                diff = f"{diff_val:+.1f}"
                            except:
                                diff = "+0"
                    else:
                        if open_odds is not None and live_decimal is not None:
                            try:
                                diff_val = int((float(live_decimal) - float(open_odds)) * 100)
                                diff = f"{diff_val:+}"
                            except:
                                diff = "+0"

                    display_open = (
                        f"{open_point} ({to_american(open_odds)})"
                        if market["key"] in ["spreads", "totals"] and open_point is not None
                        else to_american(open_odds)
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
    app.run(debug=True, host="0.0.0.0", port=5050)
