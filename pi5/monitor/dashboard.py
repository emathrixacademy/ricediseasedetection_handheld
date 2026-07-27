"""Flask dashboard exposing live system stats for the handheld scanner."""

from flask import Flask, jsonify, render_template

from .system_stats import get_stats

try:
    from config import DASHBOARD_HOST, DASHBOARD_PORT
except ImportError:  # pragma: no cover
    from pi5.config import DASHBOARD_HOST, DASHBOARD_PORT


app = Flask(__name__)

# In-memory runtime state updated by the scanning pipeline. Kept simple here;
# a real deployment would read the latest values from the database.
runtime_state = {
    "scan_count": 0,
    "last_diagnosis": "n/a",
    "last_inference_time_ms": None,
    "battery_voltage_v": None,
}


def _current_stats():
    stats = get_stats(
        battery_voltage_v=runtime_state["battery_voltage_v"],
        inference_time_ms=runtime_state["last_inference_time_ms"],
    )
    stats["scan_count"] = runtime_state["scan_count"]
    stats["last_diagnosis"] = runtime_state["last_diagnosis"]
    return stats


@app.route("/")
def index():
    return render_template("index.html", stats=_current_stats())


@app.route("/api/stats")
def api_stats():
    return jsonify(_current_stats())


if __name__ == "__main__":
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=True)
