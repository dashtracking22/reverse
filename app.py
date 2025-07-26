import os
import json
import requests
from flask import Flask, jsonify

app = Flask(__name__)

def get_redis_credentials():
    redis_url = os.getenv("REDIS_URL")
    redis_token = os.getenv("REDIS_TOKEN")
    return redis_url, redis_token

def save_to_redis(redis_url, headers, key, value):
    url = f"{redis_url}/set/{key}"
    payload = json.dumps({"value": value})
    res = requests.post(url, headers=headers, data=payload)
    return res.status_code

def get_from_redis(redis_url, headers, key):
    url = f"{redis_url}/get/{key}"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return res.json().get("result", {}).get("value")
    return None

@app.route("/")
def home():
    return "Redis test app running."

@app.route("/test_redis")
def test_redis():
    redis_url, redis_token = get_redis_credentials()
    if not redis_url or not redis_token:
        return jsonify({"error": "Redis credentials not set"}), 500

    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json"
    }

    key = "test_key"
    value = "hello from redis"

    status = save_to_redis(redis_url, headers, key, value)
    retrieved = get_from_redis(redis_url, headers, key)

    return jsonify({"saved": value, "retrieved": retrieved, "status_code": status})

if __name__ == "__main__":
    app.run(debug=True, port=5050)
