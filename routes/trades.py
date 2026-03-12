# routes/trades.py
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from datetime import date, datetime
from db.queries import (
    insert_trade, update_trade_result, get_all_trades,
    get_stats_summary, increment_session, upsert_balance
)
from core.session import get_status, today
from config import ACCOUNT_BALANCE

trades_bp = Blueprint("trades", __name__)


@trades_bp.get("/")
def journal():
    trades = get_all_trades(limit=50)
    stats  = get_stats_summary()
    return render_template("journal.html", trades=trades, stats=stats)


@trades_bp.get("/new")
def new_trade_form():
    session = get_status()
    return render_template("trade_form.html", session=session, now=datetime.now())


@trades_bp.post("/new")
def save_trade():
    f = request.form
    data = {
        "date":            f.get("date", date.today().isoformat()),
        "time":            f.get("time", datetime.now().strftime("%H:%M")),
        "direction":       f.get("direction", "LONG"),
        "bias_4h":         f.get("bias_4h", ""),
        "bias_1h":         f.get("bias_1h", ""),
        "entry_price":     float(f.get("entry_price", 0)),
        "sl_price":        float(f.get("sl_price", 0)),
        "tp_price":        float(f.get("tp_price", 0)),
        "lot_size":        float(f.get("lot_size", 0)),
        "checklist_score": int(f.get("checklist_score", 0)),
        "setup_rating":    int(f.get("setup_rating", 0)),
        "emotion":         f.get("emotion", ""),
        "notes":           f.get("notes", ""),
    }
    insert_trade(data)
    return redirect(url_for("trades.journal"))


@trades_bp.post("/close/<int:trade_id>")
def close_trade(trade_id: int):
    """Mark a trade as WIN / LOSS / BE and update session + balance."""
    f          = request.form
    exit_price = float(f.get("exit_price", 0))
    result     = f.get("result", "LOSS").upper()
    pnl        = float(f.get("pnl", 0))
    rr         = float(f.get("rr", 0))

    update_trade_result(trade_id, exit_price, result, pnl, rr)

    is_loss = result == "LOSS"
    increment_session(today(), is_loss, pnl)

    # Snapshot balance after closing the trade
    stats = get_stats_summary()
    upsert_balance(today(), ACCOUNT_BALANCE + (stats["total_pnl"] or 0))

    return redirect(url_for("trades.journal"))


@trades_bp.get("/api/all")
def api_trades():
    return jsonify(get_all_trades())


@trades_bp.get("/api/stats")
def api_stats():
    return jsonify(get_stats_summary())
