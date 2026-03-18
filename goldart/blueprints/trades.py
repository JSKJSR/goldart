# routes/trades.py
import logging
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from datetime import datetime
from goldart.database.queries import (
    insert_trade, update_trade_result, update_trade_full, delete_trade,
    get_trade, get_all_trades, get_stats_summary, get_trade_count,
)
from goldart.services.session import get_status
from goldart.services.trades import (
    calc_pnl_rr, sync_session, parse_new_trade_form, build_edit_trade_data,
)
from goldart.blueprints.decorators import get_current_user_id

log = logging.getLogger(__name__)

trades_bp = Blueprint("trades", __name__)


# ── Journal ───────────────────────────────────────────────────────────────────

@trades_bp.get("/")
def journal():
    user_id = get_current_user_id()
    page = request.args.get("page", 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    try:
        trades = get_all_trades(user_id, limit=per_page, offset=offset)
        stats = get_stats_summary(user_id)
        total = get_trade_count(user_id)
    except Exception:
        log.exception("Failed to load journal for user %s", user_id)
        trades, stats = [], {"total": 0, "wins": 0, "losses": 0,
                             "avg_rr": 0, "total_pnl": 0, "win_rate": 0}
        total = 0
    total_pages = (total + per_page - 1) // per_page if total else 1
    return render_template("journal.html", trades=trades, stats=stats,
                           page=page, total_pages=total_pages)


# ── New trade ─────────────────────────────────────────────────────────────────

@trades_bp.get("/new")
def new_trade_form():
    user_id = get_current_user_id()
    session = get_status(user_id)
    return render_template("trade_form.html", session=session, now=datetime.now())


@trades_bp.post("/new")
def save_trade():
    user_id = get_current_user_id()
    data = parse_new_trade_form(request.form, user_id)
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

    try:
        f = request.form
        exit_price = float(f.get("exit_price") or 0)
        result = f.get("result", "LOSS").upper()

        pnl, rr = calc_pnl_rr(
            entry=float(trade["entry_price"] or 0),
            exit_price=exit_price,
            sl=float(trade["sl_price"] or 0),
            lot_size=float(trade["lot_size"] or 0),
            direction=trade["direction"],
        )

        if result == "BE":
            pnl = 0.0

        update_trade_result(trade_id, exit_price, result, pnl, rr, user_id)
        sync_session(str(trade["date"]), user_id)
    except Exception:
        log.exception("Failed to close trade %s for user %s", trade_id, user_id)
        return render_template("error.html",
            title="Failed to close trade",
            message=f"Trade #{trade_id} could not be closed. Check the trade data.",
        ), 500

    return redirect(url_for("trades.journal"))


# ── Edit trade ────────────────────────────────────────────────────────────────

@trades_bp.get("/edit/<int:trade_id>")
def edit_trade_form(trade_id: int):
    user_id = get_current_user_id()
    try:
        trade = get_trade(trade_id, user_id)
    except Exception:
        log.exception("Failed to load trade %s for user %s", trade_id, user_id)
        return render_template("error.html",
            title="Could not load trade",
            message=f"Trade #{trade_id} failed to load from the database.",
        ), 500
    if not trade:
        return redirect(url_for("trades.journal"))
    return render_template("edit_trade.html", trade=trade)


@trades_bp.post("/edit/<int:trade_id>")
def edit_trade(trade_id: int):
    user_id = get_current_user_id()
    try:
        data = build_edit_trade_data(request.form, user_id)
        update_trade_full(trade_id, data)
        sync_session(data["date"], user_id)
    except Exception:
        log.exception("Failed to save edit for trade %s, user %s", trade_id, user_id)
        return render_template("error.html",
            title="Failed to save trade",
            message=f"Trade #{trade_id} could not be saved. Check your input values.",
        ), 500

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
    sync_session(trade_date, user_id)
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
