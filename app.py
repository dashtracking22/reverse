import os
import json
import requests
from flask import Flask, jsonify

app = Flask(__name__)

redis_url = os.getenv("REDIS_URL")
redis_token = os.getenv("REDIS_TOKEN")

headers = {
    "Authorization": f"Bearer {redis_token}",
    "Content-Type": "application/json"
}

@app.route("/test")
def test_redis():
    test_key = "test_key"
    test_value = "hello from test"
    try:
        # Try setting a key in Redis
        set_resp = requests.post(f"{redis_url}/set/{test_key}", headers=headers, data=json.dumps({"value": test_value}))
        # Try retrieving the key
        get_resp = requests.post(f"{redis_url}/mget", headers=headers, data=json.dumps([test_key]))
        return jsonify({
            "set_status": set_resp.status_code,
            "set_response": set_resp.text,
            "get_status": get_resp.status_code,
            "get_response": get_resp.text,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
