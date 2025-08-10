import os
import json
import time
import threading
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})

API_KEY = os.getenv("API_KEY")  # REQUIRED on Render
REGION = "us"
ODDS_FORMAT = "american"
CACHE_SECONDS = 20

ALLOWED_SPORTS = [
    "americanfootball_ncaaf",
    "americanfootball_nfl",
    "basketball_nba",
    "basketball_wnba",
    "mma_mixed_martial_arts",
    "baseball_mlb",
]

DEFAULT_BOOKMAKER = "betonlineag"
BOOKMAKERS = [
    "betonlineag",
    "draftkings",
    "fanduel",
    "caesars",
    "betmgm",
    "pointsbetus",
    "wynnbet",
]

MARKETS = ["h2h", "spreads", "totals"]

# --------- Simple cache ----------
_cache_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}

def get_cache(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            return None
        if time.time() - entry["ts"] > CACHE_SECONDS:
            return None
        return entry["data"]

def set_cache(key: str, data: Any):
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}

# --------- Persistence (Upstash Redis or local JSON) ----------
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

ODDS_LOG_PATH = "odds_log.json"
_file_lock = threading.Lock()

def _safe_load_json(path: str) -> Dict[str, Any]:
    with _file_lock:
        try:
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("{}")
            except Exception:
                pass
            return {}

def _safe_save_json(path: str, data: Dict[str, Any]):
    with _file_lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

def _redis_setnx(key: str, value: str) -> bool:
    """True if set (didn't exist). Uses Upstash REST GET endpoints or local file fallback."""
    if UPSTASH_URL and UPSTASH_TOKEN:
        url = f"{UPSTASH_URL}/setnx/{key}/{value}"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=10)  # GET avoids 405s on some setups
        r.raise_for_status()
        try:
            return bool(int(r.text.strip()))
        except Exception:
            j = r.json()
            return bool(j.get("result", 0))

    data = _safe_load_json(ODDS_LOG_PATH)
    if key in data:
        return False
    data[key] = value
    _safe_save_json(ODDS_LOG_PATH, data)
    return True

def _redis_get(key: str) -> Optional[str]:
    if UPSTASH_URL and UPSTASH_TOKEN:
        url = f"{UPSTASH_URL}/get/{key}"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        j = r.json()
        return j.get("result")
    data = _safe_load_json(ODDS_LOG_PATH)
    return data.get(key)

def _persist_opening_once(key: str, payload: Dict[str, Any]):
    value = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    _redis_setnx(key, value)

def _get_opening_payload(key: str) -> Optional[Dict[str, Any]]:
    raw = _redis_get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

# --------- Odds API ----------
BASE = "https://api.the-odds-api.com/v4"

def fetch_odds(sport: str, bookmaker: str) -> Any:
    cache_key = f"odds:{sport}:{bookmaker}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    params = {
        "apiKey": API_KEY,
        "regions": REGION,
        "markets": ",".join(MARKETS),
        "bookmakers": bookmaker,
        "oddsFormat": ODDS_FORMAT,
    }
    url = f"{BASE}/sports/{sport}/odds"
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()
    set_cache(cache_key, data)
    return data

def american_diff(curr: Optional[int], opening: Optional[int]) -> Optional[int]:
    if curr is None or opening is None:
        return None
    return curr - opening

def point_diff(curr: Optional[float], opening: Optional[float]) -> Optional[float]:
    if curr is None or opening is None:
        return None
    return round(curr - opening, 2)

def safe_int(x):
    try:
        return int(x)
    except Exception:
        return None

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

def make_key(sport: str, event_id: str, market: str, selection: str, bookmaker: str) -> str:
    sel = (selection or "").replace(" ", "_").lower()
    return f"open:{sport}:{event_id}:{market}:{sel}:{bookmaker}"

def extract_bookmaker_block(event: Dict[str, Any], bookmaker: str) -> Optional[Dict[str, Any]]:
    for bk in event.get("bookmakers", []):
        if bk.get("key") == bookmaker:
            return bk
    return None

def normalize_event_record(sport: str, event: Dict[str, Any], bookmaker: str) -> Dict[str, Any]:
    event_id = event.get("id")
    commence = event.get("commence_time")
    home = event.get("home_team")
    away = event.get("away_team")

    out = {
        "event_id": event_id,
        "commence_time": commence,
        "home_team": home,
        "away_team": away,
        "moneyline": {},
        "spreads": {},
        "totals": {}
    }

    bk = extract_bookmaker_block(event, bookmaker)
    if not bk:
        return out

    for m in bk.get("markets", []):
        mkey = m.get("key")
        outcomes = m.get("outcomes", [])
        if mkey == "h2h":
            for o in outcomes:
                name = o.get("name")
                price = safe_int(o.get("price"))
                sel_key = make_key(sport, event_id, "h2h", name, bookmaker)
                opening = _get_opening_payload(sel_key)
                if not opening:
                    _persist_opening_once(sel_key, {"opening_price": price, "ts": int(time.time())})
                    opening = {"opening_price": price}
                out["moneyline"][name] = {
                    "open": opening.get("opening_price"),
                    "live": price,
                    "diff": american_diff(price, opening.get("opening_price")),
                }

        elif mkey == "spreads":
            for o in outcomes:
                name = o.get("name")
                price = safe_int(o.get("price"))
                point = safe_float(o.get("point"))
                sel_key = make_key(sport, event_id, "spreads", name, bookmaker)
                opening = _get_opening_payload(sel_key)
                if not opening:
                    _persist_opening_once(sel_key, {
                        "opening_point": point,
                        "opening_price": price,
                        "ts": int(time.time())
                    })
                    opening = {"opening_point": point, "opening_price": price}
                out["spreads"][name] = {
                    "open_point": opening.get("opening_point"),
                    "open_price": opening.get("opening_price"),
                    "live_point": point,
                    "live_price": price,
                    "diff_point": point_diff(point, opening.get("opening_point")),
                }

        elif mkey == "totals":
            for o in outcomes:
                name = o.get("name")
                price = safe_int(o.get("price"))
                point = safe_float(o.get("point"))
                sel_key = make_key(sport, event_id, "totals", name, bookmaker)
                opening = _get_opening_payload(sel_key)
                if not opening:
                    _persist_opening_once(sel_key, {
                        "opening_point": point,
                        "opening_price": price,
                        "ts": int(time.time())
                    })
                    opening = {"opening_point": point, "opening_price": price}
                out["totals"][name] = {
                    "open_point": opening.get("opening_point"),
                    "open_price": opening.get("opening_price"),
                    "live_point": point,
                    "live_price": price,
                    "diff_point": point_diff(point, opening.get("opening_point")),
                }

    return out

# ------------------ Routes ------------------

@app.route("/")
def root():
    return send_from_directory("templates", "betkarma2.html")

@app.route("/sports")
def sports():
    # Log hits so we can see this in Render logs
    app.logger.info("HIT /sports")
    try:
        r = requests.get(
            f"{BASE}/sports",
            params={"apiKey": API_KEY, "all": "false"},
            timeout=15
        )
        r.raise_for_status()
        arr = r.json()
        keys = [x.get("key") for x in arr if x.get("active")]
        keys = [k for k in keys if k in ALLOWED_SPORTS]
        app.logger.info("Returning %d sports", len(keys))
        return jsonify({"sports": keys})
    except Exception as e:
        app.logger.warning("Sports fallback due to error: %s", e)
        return jsonify({"sports": ALLOWED_SPORTS, "note": "fallback"}), 200

@app.route("/bookmakers")
def bookmakers():
    return jsonify({"bookmakers": BOOKMAKERS, "default": DEFAULT_BOOKMAKER})

@app.route("/odds/<sport>")
def odds_for_sport(sport: str):
    if sport not in ALLOWED_SPORTS:
        return jsonify({"error": "Unsupported sport"}), 400
    bookmaker = request.args.get("bookmaker", DEFAULT_BOOKMAKER)
    if not API_KEY:
        return jsonify({"error": "API_KEY missing"}), 500
    try:
        data = fetch_odds(sport, bookmaker)
        records = [normalize_event_record(sport, e, bookmaker) for e in data]
        def _ts(x):
            try:
                return datetime.fromisoformat(x.get("commence_time").replace("Z",""))
            except Exception:
                return datetime.max
        records.sort(key=_ts)
        return jsonify({"sport": sport, "bookmaker": bookmaker, "records": records})
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else 500
        return jsonify({"error": "Odds API error", "status": status, "details": str(e)}), status
    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))  # Render provides PORT
    app.run(host="0.0.0.0", port=port, debug=True)
