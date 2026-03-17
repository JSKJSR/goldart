# routes/trades.py
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from datetime import date, datetime
from goldart.database.queries import (
    insert_trade, update_trade_result, update_trade_full, delete_trade,
    get_trade, get_all_trades, get_stats_summary,
    get_trades_by_date, get_or_create_session, upsert_balance,
)
from goldart.services.session import get_status
from goldart.config import ACCOUNT_BALANCE
from goldart.blueprints.decorators import get_current_user_id

trades_bp = Blueprint("trades", __name__)

# Gold: 1 lot = 100 oz → $100 PnL per $1 price move per lot
_PIP_VALUE = 100.0


def _calc_pnl_rr(entry: float, exit_price: float, sl: float,
                 lot_size: float, direction: str) -> tuple[float, float]:
    """Auto-calculate PnL ($) and RR from prices — no manual entry needed."""
    mult = 1.0 if direction == "LONG" else -1.0
    pnl  = round((exit_price - entry) * mult * lot_size * _PIP_VALUE, 2)
    sl_dist = abs(entry - sl)
    rr = round(abs(exit_price - entry) / sl_dist, 2) if sl_dist > 0 else 0.0
    return pnl, rr


def _sync_session(date_str: str, user_id: int):
    """Recompute session counters from actual trades for the given date."""
    from goldart.database.queries import _db
    trades = get_trades_by_date(date_str, user_id)
    closed = [t for t in trades if t.get("result")]
    trades_taken = len(closed)
    losses_taken = sum(1 for t in closed if t["result"] == "LOSS")
    daily_pnl = round(sum(t.get("pnl") or 0 for t in closed), 2)

    # Ensure session row exists then overwrite counters
    get_or_create_session(date_str, user_id)
    with _db() as cur:
        cur.execute("""
            UPDATE sessions
            SET trades_taken = %s, losses_taken = %s, daily_pnl = %s
            WHERE date = %s AND user_id = %s
        """, (trades_taken, losses_taken, daily_pnl, date_str, user_id))

    # Update account balance
    stats = get_stats_summary(user_id)
    upsert_balance(date_str, user_id, ACCOUNT_BALANCE + float(stats["total_pnl"] or 0))


# ── Journal ───────────────────────────────────────────────────────────────────

@trades_bp.get("/")
def journal():
    user_id = get_current_user_id()
    trades = get_all_trades(user_id, limit=50)
    stats  = get_stats_summary(user_id)
    return render_template("journal.html", trades=trades, stats=stats)


# ── New trade ─────────────────────────────────────────────────────────────────

@trades_bp.get("/new")
def new_trade_form():
    user_id = get_current_user_id()
    session = get_status(user_id)
    return render_template("trade_form.html", session=session, now=datetime.now())


@trades_bp.post("/new")
def save_trade():
    user_id = get_current_user_id()
    f = request.form
    data = {
        "user_id":         user_id,
        "date":            f.get("date", date.today().isoformat()),
        "time":            f.get("time", datetime.now().strftime("%H:%M")),
        "direction":       f.get("direction", "LONG"),
        "bias_4h":         f.get("bias_4h", ""),
        "bias_1h":         f.get("bias_1h", ""),
        "entry_price":     float(f.get("entry_price") or 0),
        "sl_price":        float(f.get("sl_price") or 0),
        "tp_price":        float(f.get("tp_price") or 0),
        "lot_size":        float(f.get("lot_size") or 0),
        "checklist_score": int(f.get("checklist_score") or 0),
        "setup_rating":    int(f.get("setup_rating") or 0),
        "emotion":         f.get("emotion", ""),
        "notes":           f.get("notes", ""),
    }
    insert_trade(data)
    return redirect(url_for("trades.journal"))


# ── Close trade (auto-calculates PnL) ────────────────────────────────────────

@trades_bp.post("/close/<int:trade_id>")
def close_trade(trade_id: int):
    """Close an open trade — PnL and RR are calculated server-side."""
    user_id = get_current_user_id()
    trade = get_trade(trade_id, user_id)
    if not trade:
        return redirect(url_for("trades.journal"))

    f          = request.form
    exit_price = float(f.get("exit_price") or 0)
    result     = f.get("result", "LOSS").upper()

    pnl, rr = _calc_pnl_rr(
        entry      = trade["entry_price"],
        exit_price = exit_price,
        sl         = trade["sl_price"],
        lot_size   = trade["lot_size"],
        direction  = trade["direction"],
    )

    # BE override: force PnL to 0
    if result == "BE":
        pnl = 0.0

    update_trade_result(trade_id, exit_price, result, pnl, rr, user_id)

    # Recompute session from actual trades (reliable, replaces increment)
    _sync_session(trade["date"], user_id)

    return redirect(url_for("trades.journal"))


# ── Edit trade ────────────────────────────────────────────────────────────────

@trades_bp.get("/edit/<int:trade_id>")
def edit_trade_form(trade_id: int):
    user_id = get_current_user_id()
    trade = get_trade(trade_id, user_id)
    if not trade:
        return redirect(url_for("trades.journal"))
    return render_template("edit_trade.html", trade=trade)


@trades_bp.post("/edit/<int:trade_id>")
def edit_trade(trade_id: int):
    user_id     = get_current_user_id()
    f           = request.form
    exit_raw    = f.get("exit_price", "").strip()
    result_raw  = f.get("result", "").strip().upper() or None

    entry     = float(f.get("entry_price") or 0)
    sl        = float(f.get("sl_price") or 0)
    lot_size  = float(f.get("lot_size") or 0)
    direction = f.get("direction", "LONG")

    # Auto-calculate PnL/RR if exit price is supplied
    if exit_raw and result_raw:
        exit_price = float(exit_raw)
        pnl, rr = _calc_pnl_rr(entry, exit_price, sl, lot_size, direction)
        if result_raw == "BE":
            pnl = 0.0
    else:
        exit_price = float(exit_raw) if exit_raw else None
        pnl = float(f.get("pnl") or 0)
        rr  = float(f.get("rr_achieved") or 0)

    data = {
        "user_id":         user_id,
        "date":            f.get("date", date.today().isoformat()),
        "time":            f.get("time", "00:00"),
        "direction":       direction,
        "bias_4h":         f.get("bias_4h", ""),
        "bias_1h":         f.get("bias_1h", ""),
        "entry_price":     entry,
        "sl_price":        sl,
        "tp_price":        float(f.get("tp_price") or 0),
        "lot_size":        lot_size,
        "exit_price":      exit_price,
        "result":          result_raw,
        "pnl":             pnl,
        "rr_achieved":     rr,
        "checklist_score": int(f.get("checklist_score") or 0),
        "setup_rating":    int(f.get("setup_rating") or 3),
        "emotion":         f.get("emotion", ""),
        "notes":           f.get("notes", ""),
    }
    update_trade_full(trade_id, data)

    # Recompute session stats from actual trades for today
    _sync_session(data["date"], user_id)

    return redirect(url_for("trades.journal"))


# ── Delete trade ──────────────────────────────────────────────────────────────

@trades_bp.post("/delete/<int:trade_id>")
def delete_trade_route(trade_id: int):
    user_id = get_current_user_id()
    trade = get_trade(trade_id, user_id)
    if not trade:
        return redirect(url_for("trades.journal"))

    trade_date = trade["date"]
    delete_trade(trade_id, user_id)
    _sync_session(trade_date, user_id)
    return redirect(url_for("trades.journal"))


# ── API ───────────────────────────────────────────────────────────────────────

@trades_bp.get("/api/all")
def api_trades():
    user_id = get_current_user_id()
    return jsonify(get_all_trades(user_id))


@trades_bp.get("/api/stats")
def api_stats():
    user_id = get_current_user_id()
    return jsonify(get_stats_summary(user_id))
