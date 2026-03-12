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

    return render_template(
        "dashboard.html",
        session=session,
        trades=trades,
        stats=stats,
        history=history,
    )
