import os
import json
import time
import threading
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

API_KEY = os.getenv("API_KEY")  # <-- set this in your env; do NOT hardcode
REGION = "us"
ODDS_FORMAT = "american"  # ensure prices come back as American
CACHE_SECONDS = 20

ALLOWED_SPORTS = [
    "baseball_mlb",
    "mma_mixed_martial_arts",
    "basketball_wnba",
    "americanfootball_nfl",
    "americanfootball_ncaaf"
]

DEFAULT_BOOKMAKER = "betonlineag"
BOOKMAKERS = [
    "betonlineag",
    "draftkings",
    "fanduel",
    "caesars",
    "betmgm",
    "pointsbetus",
    "wynnbet"
]

MARKETS = ["h2h", "spreads", "totals"]

# --------- Simple in-process cache to reduce API calls ----------
_cache_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}  # {key: {"data":..., "ts":...}}

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

# --------- Persistence (Redis via Upstash REST or local JSON) ----------
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
            # recover by resetting bad file
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
    """
    Returns True if key was set (did not exist), False if it already existed.
    Uses Upstash REST if configured; otherwise local JSON with set-once semantics.
    """
    if UPSTASH_URL and UPSTASH_TOKEN:
        url = f"{UPSTASH_URL}/setnx/{key}/{value}"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        r = requests.post(url, headers=headers, timeout=10)
        r.raise_for_status()
        # Upstash returns integer 1/0
        try:
            return bool(int(r.text.strip()))
        except Exception:
            # Some deployments return JSON like {"result":1}
            j = r.json()
            return bool(j.get("result", 0))

    # Fallback: local file set-once
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
        # Upstash returns JSON like {"result":"..."} or nil
        j = r.json()
        return j.get("result")
    data = _safe_load_json(ODDS_LOG_PATH)
    val = data.get(key)
    return val

def _persist_opening_once(key: str, payload: Dict[str, Any]):
    """
    payload stored as JSON string under immutable key via SETNX semantics.
    """
    value = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    _redis_setnx(key, value)  # ignore return; we only need it set once

def _get_opening_payload(key: str) -> Optional[Dict[str, Any]]:
    raw = _redis_get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

# --------- Odds API helpers ----------
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
        "oddsFormat": ODDS_FORMAT
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
    # Show with sign (e.g., -2.5 -> -3.5 = -1.0)
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
    # Normalize selection to avoid spaces issues in Redis keys
    sel = selection.replace(" ", "_").lower()
    return f"open:{sport}:{event_id}:{market}:{sel}:{bookmaker}"

def extract_bookmaker_block(event: Dict[str, Any], bookmaker: str) -> Optional[Dict[str, Any]]:
    for bk in event.get("bookmakers", []):
        if bk.get("key") == bookmaker:
            return bk
    return None

def normalize_event_record(sport: str, event: Dict[str, Any], bookmaker: str) -> Dict[str, Any]:
    """
    Produce one consolidated record with:
    - moneyline (per team)
    - spreads (per team with point)
    - totals (Over/Under with point)
    Persist and read opening odds as needed.
    """
    event_id = event.get("id")
    commence = event.get("commence_time")
    home = event.get("home_team")
    away = event.get("away_team")

    out = {
        "event_id": event_id,
        "commence_time": commence,
        "home_team": home,
        "away_team": away,
        "moneyline": {},  # {team: {open, live, diff}}
        "spreads": {},    # {team: {open_point, open_price, live_point, live_price, diff_point}}
        "totals": {}      # {"Over": {...}, "Under": {...}}
    }

    bk = extract_bookmaker_block(event, bookmaker)
    if not bk:
        return out

    for m in bk.get("markets", []):
        mkey = m.get("key")  # "h2h", "spreads", "totals"
        outcomes = m.get("outcomes", [])
        if mkey == "h2h":
            for o in outcomes:
                name = o.get("name")
                price = safe_int(o.get("price"))
                sel_key = make_key(sport, event_id, "h2h", name, bookmaker)
                opening = _get_opening_payload(sel_key)
                if not opening:
                    _persist_opening_once(sel_key, {
                        "opening_price": price,
                        "ts": int(time.time())
                    })
                    opening = {"opening_price": price}
                out["moneyline"][name] = {
                    "open": opening.get("opening_price"),
                    "live": price,
                    "diff": american_diff(price, opening.get("opening_price"))
                }

        elif mkey == "spreads":
            for o in outcomes:
                name = o.get("name")  # team name
                price = sa
