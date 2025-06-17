from flask import Flask, request, render_template, jsonify
from analyzer import analyze_urls

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    urls = request.json.get("urls", [])
    results = analyze_urls(urls)
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
