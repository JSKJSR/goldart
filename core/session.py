# core/session.py — enforces daily trading rules
from datetime import date
from config import MAX_TRADES_PER_DAY, MAX_LOSSES_PER_DAY
from db.queries import get_or_create_session, set_session_status


def today() -> str:
    return date.today().isoformat()


def get_status() -> dict:
    """
    Returns current session state + whether trading is allowed.
    Called on every page load — thin and fast.
    """
    s = get_or_create_session(today())

    trades_left  = MAX_TRADES_PER_DAY - s["trades_taken"]
    losses_left  = MAX_LOSSES_PER_DAY - s["losses_taken"]
    can_trade    = trades_left > 0 and losses_left > 0 and s["status"] == "ACTIVE"

    block_reason = None
    if losses_left <= 0:
        block_reason = "Max daily losses reached (2). Trading locked."
        _lock(s["date"], "MAX_LOSS")
    elif trades_left <= 0:
        block_reason = "Max daily trades reached (3). Trading locked."
        _lock(s["date"], "MAX_TRADES")

    return {
        "date":         s["date"],
        "trades_taken": s["trades_taken"],
        "losses_taken": s["losses_taken"],
        "daily_pnl":    s["daily_pnl"],
        "status":       s["status"],
        "trades_left":  max(trades_left, 0),
        "losses_left":  max(losses_left, 0),
        "can_trade":    can_trade,
        "block_reason": block_reason,
        "max_trades":   MAX_TRADES_PER_DAY,
        "max_losses":   MAX_LOSSES_PER_DAY,
    }


def _lock(date_str: str, status: str):
    s = get_or_create_session(date_str)
    if s["status"] == "ACTIVE":
        set_session_status(date_str, status)
