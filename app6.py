import os
import json
import time
import threading
from datetime import datetime
from typing import Any, Dict, Optional, List, Tuple

import requests
from requests.adapters import HTTPAdapter
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})

API_KEY = os.getenv("API_KEY")  # REQUIRED on Render
REGION = "us"
ODDS_FORMAT = "american"
CACHE_SECONDS = 60

# Sports keys (primary uses americanfootball_ncaa; tolerate _ncaaf)
ALLOWED_SPORTS = [
    "americanfootball_ncaa",
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

# --------- HTTP connection pooling ----------
HTTP = requests.Session()
HTTP.mount("https://", HTTPAdapter(pool_connections=50, pool_maxsize=50))
HTTP.mount("http://", HTTPAdapter(pool_connections=50, pool_maxsize=50))

# --------- Simple in-proc cache ----------
_cache_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}
def get_cache(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if not entry: return None
        if time.time() - entry["ts"] > CACHE_SECONDS: return None
        return entry["data"]
def set_cache(key: str, data: Any):
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}

# --------- Opening odds store (RAM/file, plus Redis setnx as source of truth) ----------
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
ODDS_LOG_PATH = "odds_log.json"

_file_lock = threading.Lock()

def _load_file_dict(path: str) -> Dict[str, Any]:
    with _file_lock:
        try:
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}

def _save_file_dict(path: str, data: Dict[str, Any]):
    with _file_lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

def _redis_get(key: str) -> Optional[str]:
    """Fetch a single key from Upstash Redis (GET)."""
    if not (UPSTASH_URL and UPSTASH_TOKEN):
        return None
    try:
        r = HTTP.get(
            f"{UPSTASH_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=3,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        j = r.json()
        return j.get("result")
    except Exception:
        return None

# Async Redis writer (non-blocking setnx)
_redis_queue: List[Tuple[str, str]] = []
_redis_q_lock = threading.Lock()
_redis_worker_started = False

def _start_redis_worker():
    global _redis_worker_started
    if _redis_worker_started or not (UPSTASH_URL and UPSTASH_TOKEN):
        return
    _redis_worker_started = True
    def _worker():
        while True:
            try:
                batch = []
                with _redis_q_lock:
                    if _redis_queue:
                        batch = _redis_queue[:500]
                        del _redis_queue[:500]
                if not batch:
                    time.sleep(0.5)
                    continue
                for k, v in batch:
                    try:
                        url = f"{UPSTASH_URL}/setnx/{k}/{v}"
                        HTTP.get(url, headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}, timeout=5)
                    except Exception:
                        pass
            except Exception:
                time.sleep(1.0)
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

_start_redis_worker()

class OpeningsStore:
    """
    Request-scoped store:
      - Loads local file dict once.
      - get(key): RAM -> file -> Redis(GET). If Redis returns a value, memoize it in RAM (and keep file clean).
      - setnx(key, payload): record in RAM; flush to file at end; queue Redis SETNX async.
      - flush_if_needed(): writes file once if anything new was added.
    """
    def __init__(self):
        self._dict = _load_file_dict(ODDS_LOG_PATH)
        self._dirty = False

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        raw = self._dict.get(key)
        if raw:
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except Exception:
                    return None
            return raw

        # Not in file: try Redis GET once (fast path for cross-restart or multi-instance)
        raw_redis = _redis_get(key)
        if raw_redis:
            try:
                parsed = json.loads(raw_redis)
            except Exception:
                return None
            # memoize in RAM dict (do not mark dirty; we didn't create it)
            self._dict[key] = parsed
            return parsed

        return None

    def setnx(self, key: str, payload: Dict[str, Any]):
        if key in self._dict:
            return
        # write-through to memory (for the remainder of this request)
        self._dict[key] = payload
        self._dirty = True
        # queue Redis write (stringify)
        try:
            if UPSTASH_URL and UPSTASH_TOKEN:
                v = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                with _redis_q_lock:
                    _redis_queue.append((key, v))
        except Exception:
            pass

    def flush_if_needed(self):
        if self._dirty:
            _save_file_dict(ODDS_LOG_PATH, self._dict)
            self._dirty = False

# --------- Odds API ----------
BASE = "https://api.the-odds-api.com/v4"
def fetch_odds(sport: str, bookmaker: str) -> Any:
    cache_key = f"odds_raw:{sport}:{bookmaker}"
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
    r = HTTP.get(url, params=params, timeout=25)
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

def normalize_event_record(
    store: OpeningsStore,
    sport: str,
    event: Dict[str, Any],
    bookmaker: str
) -> Dict[str, Any]:
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
                opening = store.get(sel_key)
                if not opening:
                    opening = {"opening_price": price, "ts": int(time.time())}
                    store.setnx(sel_key, opening)
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
                opening = store.get(sel_key)
                if not opening:
                    opening = {"opening_point": point, "opening_price": price, "ts": int(time.time())}
                    store.setnx(sel_key, opening)
                out["spreads"][name] = {
                    "open_point": opening.get("opening_point"),
                    "open_price": opening.get("opening_price"),
                    "live_point": point,
                    "live_price": price,
                    "diff_point": point_diff(point, opening.get("opening_point")),
                }

        elif mkey == "totals":
            for o in outcomes:
                name = o.get("name")  # "Over"/"Under"
                price = safe_int(o.get("price"))
                point = safe_float(o.get("point"))
                sel_key = make_key(sport, event_id, "totals", name, bookmaker)
                opening = store.get(sel_key)
                if not opening:
                    opening = {"opening_point": point, "opening_price": price, "ts": int(time.time())}
                    store.setnx(sel_key, opening)
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
    """Normalize to your allow-list; map ncaaf -> ncaa if upstream uses it."""
    try:
        r = HTTP.get(
            f"{BASE}/sports",
            params={"apiKey": API_KEY, "all": "false"},
            timeout=15
        )
        r.raise_for_status()
        arr = r.json()
        keys = [x.get("key") for x in arr if x.get("active")]
        mapped = []
        for k in keys:
            if k == "americanfootball_ncaaf":
                mapped.append("americanfootball_ncaa")
            else:
                mapped.append(k)
        mapped = [k for k in mapped if k in ALLOWED_SPORTS]
        return jsonify({"sports": mapped})
    except Exception:
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
        store = OpeningsStore()
        records = [normalize_event_record(store, sport, e, bookmaker) for e in data]
        def _ts(x):
            try:
                return datetime.fromisoformat(x.get("commence_time").replace("Z",""))
            except Exception:
                return datetime.max
        records.sort(key=_ts)
        store.flush_if_needed()
        return jsonify({"sport": sport, "bookmaker": bookmaker, "records": records})
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else 500
        return jsonify({"error": "Odds API error", "status": status, "details": str(e)}), status
    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500

@app.route("/routes")
def routes():
    try:
        rules = []
        for r in app.url_map.iter_rules():
            methods = ",".join(sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS")))
            rules.append({"rule": str(r), "endpoint": r.endpoint, "methods": methods})
        return jsonify({"routes": rules})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=True)
