# routes/dashboard.py
import logging
from flask import Blueprint, render_template
from goldart.services.session import get_status
from goldart.database.queries import (
    get_trades_by_date, get_stats_summary, get_balance_history,
    get_current_streak, get_open_trades_count,
)
from goldart.blueprints.decorators import get_current_user_id
from goldart.config import ACCOUNT_BALANCE
from datetime import date

log = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    user_id   = get_current_user_id()
    today_str = date.today().isoformat()

    try:
        session = get_status(user_id)
        trades  = get_trades_by_date(today_str, user_id)
        stats   = get_stats_summary(user_id)
        history = get_balance_history(user_id, 30)
        streak  = get_current_streak(user_id)
        open_count = get_open_trades_count(user_id)
    except Exception:
        log.exception("Dashboard load failed for user %s", user_id)
        return render_template("error.html",
            title="Dashboard failed to load",
            message="Could not connect to the database or load your data.",
        ), 500

    # Recompute session counters from actual trades (source of truth)
    closed = [t for t in trades if t.get("result")]
    session["trades_taken"] = len(closed)
    session["losses_taken"] = sum(1 for t in closed if t["result"] == "LOSS")
    session["daily_pnl"]    = round(sum(float(t.get("pnl") or 0) for t in closed), 2)
    session["trades_left"]  = max(session["max_trades"] - session["trades_taken"], 0)
    session["losses_left"]  = max(session["max_losses"] - session["losses_taken"], 0)
    session["can_trade"]    = session["trades_left"] > 0 and session["losses_left"] > 0

    # Compute equity curve points from balance history
    equity_points = []
    if history:
        for h in reversed(history):
            equity_points.append({"date": h["date"], "balance": float(h["balance"])})

    balance = ACCOUNT_BALANCE + stats["total_pnl"]

    return render_template(
        "dashboard.html",
        session=session,
        trades=trades,
        stats=stats,
        history=history,
        streak=streak,
        open_count=open_count,
        equity_points=equity_points,
        balance=balance,
    )
