# routes/analysis.py
from flask import Blueprint, render_template, jsonify, request
from core.data import fetch_ohlcv, DataFetchError
from core.signals import analyse
from core.risk import calculate
from core.session import get_status
from core import cache
from config import SYMBOL

analysis_bp  = Blueprint("analysis", __name__)
SNAPSHOT_KEY = "snapshot"


@analysis_bp.get("/")
def index():
    session = get_status()
    return render_template("analysis.html", symbol=SYMBOL, session=session)


@analysis_bp.get("/api/snapshot")
def snapshot():
    """
    Returns cached analysis if fresh (< 60s), otherwise fetches live data.
    Credits used per fresh fetch: 3 (4H + 1H + 15M).
    Price is taken from df_15m last close — no extra API call needed.
    """
    cached = cache.get(SNAPSHOT_KEY)
    if cached:
        # Return stale data with cache metadata — no API call
        return jsonify({
            "ok":        True,
            "data":      cached,
            "cached":    True,
            "age":       cache.age(SNAPSHOT_KEY),
            "refresh_in": cache.remaining(SNAPSHOT_KEY),
        })

    try:
        df_4h  = fetch_ohlcv("4h")
        df_1h  = fetch_ohlcv("1h")
        df_15m = fetch_ohlcv("15min")
        data   = analyse(df_1h, df_4h, df_15m)

        # Use last 15M close as price — saves 1 API credit vs get_current_price()
        data["price"] = data["current_price"]

        cache.set(SNAPSHOT_KEY, data)

        return jsonify({
            "ok":         True,
            "data":       data,
            "cached":     False,
            "age":        0,
            "refresh_in": cache.remaining(SNAPSHOT_KEY),
        })

    except DataFetchError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@analysis_bp.post("/api/risk")
def risk():
    """JSON endpoint — calculates lot size from entry + SL."""
    body      = request.get_json(silent=True) or {}
    entry     = body.get("entry")
    sl        = body.get("sl")
    direction = body.get("direction", "LONG")

    if not entry or not sl:
        return jsonify({"ok": False, "error": "entry and sl required"}), 400

    result = calculate(float(entry), float(sl), direction.upper())
    return jsonify({"ok": True, "data": result})
