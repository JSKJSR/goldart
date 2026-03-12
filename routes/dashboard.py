# routes/dashboard.py
from flask import Blueprint, render_template
from core.session import get_status
from db.queries import get_trades_by_date, get_stats_summary, get_balance_history
from datetime import date

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    session   = get_status()
    today_str = date.today().isoformat()
    trades    = get_trades_by_date(today_str)
    stats     = get_stats_summary()
    history   = get_balance_history(30)

    # Recompute session counters from actual trades (source of truth)
    closed = [t for t in trades if t.get("result")]
    session["trades_taken"] = len(closed)
    session["losses_taken"] = sum(1 for t in closed if t["result"] == "LOSS")
    session["daily_pnl"]    = round(sum(t.get("pnl") or 0 for t in closed), 2)
    session["trades_left"]  = max(session["max_trades"] - session["trades_taken"], 0)
    session["losses_left"]  = max(session["max_losses"] - session["losses_taken"], 0)
    session["can_trade"]    = session["trades_left"] > 0 and session["losses_left"] > 0

    return render_template(
        "dashboard.html",
        session=session,
        trades=trades,
        stats=stats,
        history=history,
    )
