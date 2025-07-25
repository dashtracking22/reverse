from flask import Flask, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

API_KEY = "e9cb3bfd5865b71161c903d24911b88d"

@app.route("/odds/<sport>")
def get_odds(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?regions=us&markets=h2h&bookmakers=betonlineag&apiKey={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        print(f"\n✅ RAW ODDS for {sport}:")
        print(data)

        return jsonify(data)
    except Exception as e:
        print(f"❌ Error fetching odds for {sport}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/sports")
def get_sports():
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        print(f"❌ Error fetching sports: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5050)
