# ✅ app7.py (Flask backend)
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from redis import Redis
import os
import requests
import json
from datetime import datetime

app = Flask(__name__, static_folder='static')
CORS(app)

redis = Redis(
    host=os.environ.get('REDIS_HOST'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    password=os.environ.get('REDIS_PASSWORD'),
    decode_responses=True
)

API_KEY = os.environ.get("THE_ODDS_API_KEY")
BOOKMAKER = "betonlineag"

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/sports')
def get_sports():
    return jsonify([
        "baseball_mlb",
        "basketball_wnba",
        "mma_mixed_martial_arts",
        "americanfootball_nfl",
        "americanfootball_ncaaf"
    ])

@app.route('/odds/<sport>')
def get_odds(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?regions=us&markets=h2h,spreads,totals&bookmakers={BOOKMAKER}&apiKey={API_KEY}"
    try:
        response = requests.get(url)
        games = response.json()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    result = []
    for game in games:
        game_id = f"{sport}:{game['home_team']} vs {game['away_team']}"
        timestamp = game.get('commence_time', '')
        est_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%m/%d %I:%M %p") if timestamp else ""

        entry = {
            "matchup": f"{game['away_team']} vs {game['home_team']}",
            "time": est_time,
            "moneyline": {},
            "spread": {},
            "total": {}
        }

        for market in game.get('bookmakers', [])[0].get('markets', []):
            if market['key'] == 'h2h':
                for outcome in market['outcomes']:
                    entry['moneyline'][outcome['name']] = {
                        "price": outcome['price']
                    }
            elif market['key'] == 'spreads':
                for outcome in market['outcomes']:
                    entry['spread'][outcome['name']] = {
                        "point": outcome.get('point'),
                        "price": outcome.get('price')
                    }
            elif market['key'] == 'totals':
                for outcome in market['outcomes']:
                    entry['total'][outcome['name']] = {
                        "point": outcome.get('point'),
                        "price": outcome.get('price')
                    }

        key = f"opening_odds:{game_id}"
        if not redis.exists(key):
            redis.set(key, json.dumps(entry))

        try:
            opening = json.loads(redis.get(key))
        except:
            opening = entry

        entry['opening'] = opening
        result.append(entry)

    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)
