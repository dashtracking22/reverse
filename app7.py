from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import requests
import os
from datetime import datetime
import pytz

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

API_KEY = os.getenv('API_KEY')
REDIS_URL = os.getenv('REDIS_URL')
REDIS_TOKEN = os.getenv('REDIS_TOKEN')

MARKETS = ['h2h', 'spreads', 'totals']

headers = {
    "Authorization": f"Bearer {REDIS_TOKEN}",
    "Content-Type": "application/json"
}

@app.route('/')
def index():
    return render_template('index.html')

def fetch_from_redis(key):
    try:
        response = requests.get(f"{REDIS_URL}/get/{key}", headers=headers)
        data = response.json()
        return data.get('result')
    except Exception:
        return None

def save_to_redis(key, value):
    try:
        requests.post(f"{REDIS_URL}/set/{key}", json={"value": value}, headers=headers)
    except Exception:
        pass

def american_odds(decimal_odds):
    if decimal_odds is None:
        return None
    try:
        decimal_odds = float(decimal_odds)
        if decimal_odds >= 2.0:
            return f"+{int((decimal_odds - 1) * 100)}"
        else:
            return f"-{int(100 / (decimal_odds - 1))}"
    except:
        return None

def format_game_data(game, market_data):
    game_id = game['id']
    sport_key = game['sport_key']
    commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
    est_time = commence_time.astimezone(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d %I:%M %p')

    home_team = game['home_team']
    away_team = [team for team in game['teams'] if team != home_team][0]
    matchup = f"{away_team} @ {home_team}"

    result = {
        'matchup': matchup,
        'commence_time': est_time,
        'moneyline': {},
        'spread': {},
        'total': {}
    }

    for market in market_data:
        if market['key'] not in MARKETS:
            continue

        outcomes = market['outcomes']
        result[market['key'].replace('h2h', 'moneyline')] = extract_market_data(
            game_id, sport_key, market['key'], outcomes, is_point_based=(market['key'] != 'h2h')
        )

    return result

def extract_market_data(game_id, sport_key, label, outcomes, is_point_based):
    data = {}
    open_key = f"{sport_key}:{game_id}:{label}:open"
    current_lines = {}
    open_lines = {}

    for outcome in outcomes:
        name = outcome['name']
        point = outcome.get('point')
        price = outcome.get('price')
        current_lines[name] = {'point': point, 'price': price}

    existing = fetch_from_redis(open_key)
    if existing is None:
        save_to_redis(open_key, current_lines)
        open_lines = current_lines
    else:
        try:
            open_lines = eval(existing)
        except:
            open_lines = current_lines

    for name in current_lines:
        open_price = open_lines.get(name, {}).get('price')
        live_price = current_lines[name].get('price')
        open_point = open_lines.get(name, {}).get('point')
        live_point = current_lines[name].get('point')
        open_american = american_odds(open_price)
        live_american = american_odds(live_price)

        diff = None
        if is_point_based and open_point is not None and live_point is not None:
            try:
                diff = round(float(live_point) - float(open_point), 1)
            except:
                diff = None

        data[name] = {
            'open': f"{open_point if is_point_based else ''} ({open_american})",
            'live': f"{live_point if is_point_based else ''} ({live_american})",
            'diff': diff if diff is not None else "-"
        }

    return data

@app.route('/sports')
def get_sports():
    return jsonify([
        {"key": "baseball_mlb", "title": "MLB"},
        {"key": "americanfootball_nfl", "title": "NFL"},
        {"key": "americanfootball_ncaaf", "title": "NCAAF"},
        {"key": "basketball_wnba", "title": "WNBA"},
        {"key": "mma_mixed_martial_arts", "title": "MMA"}
    ])

@app.route('/odds/<sport>')
def get_odds(sport):
    bookmaker = request.args.get('bookmaker', 'betonlineag')
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?regions=us&markets={','.join(MARKETS)}&bookmakers={bookmaker}&apiKey={API_KEY}"
    response = requests.get(url)
    games = response.json()

    output = []
    for game in games:
        if 'bookmakers' not in game or not game['bookmakers']:
            continue
        bookmaker_data = game['bookmakers'][0]
        game_data = format_game_data(game, bookmaker_data.get('markets', []))
        output.append(game_data)

    return jsonify(output)

if __name__ == '__main__':
    app.run(debug=True, port=5050)
