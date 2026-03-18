from __future__ import annotations

from datetime import date, datetime
from goldart.database.queries import (
    get_trades_by_date, get_or_create_session, update_session_counters,
    get_stats_summary, upsert_balance,
)
from goldart.config import ACCOUNT_BALANCE

# Gold: 1 lot = 100 oz -> $100 PnL per $1 price move per lot
# (same constant as risk.py — pip_value_per_lot)
_PIP_VALUE = 100.0


def calc_pnl_rr(entry: float, exit_price: float, sl: float,
                lot_size: float, direction: str) -> tuple[float, float]:
    """Auto-calculate PnL ($) and RR from prices."""
    mult = 1.0 if direction == "LONG" else -1.0
    pnl = round((exit_price - entry) * mult * lot_size * _PIP_VALUE, 2)
    sl_dist = abs(entry - sl)
    rr = round(abs(exit_price - entry) / sl_dist, 2) if sl_dist > 0 else 0.0
    return pnl, rr


def sync_session(date_str: str, user_id: int):
    """Recompute session counters from actual trades for the given date."""
    trades = get_trades_by_date(date_str, user_id)
    closed = [t for t in trades if t.get("result")]
    trades_taken = len(closed)
    losses_taken = sum(1 for t in closed if t["result"] == "LOSS")
    daily_pnl = round(sum(t.get("pnl") or 0 for t in closed), 2)

    get_or_create_session(date_str, user_id)
    update_session_counters(date_str, user_id, trades_taken, losses_taken, daily_pnl)

    stats = get_stats_summary(user_id)
    upsert_balance(date_str, user_id, ACCOUNT_BALANCE + float(stats["total_pnl"] or 0))


def parse_new_trade_form(form, user_id: int) -> dict:
    """Extract new-trade data from a Flask form."""
    return {
        "user_id":         user_id,
        "date":            form.get("date", date.today().isoformat()),
        "time":            form.get("time", datetime.now().strftime("%H:%M")),
        "direction":       form.get("direction", "LONG"),
        "bias_4h":         form.get("bias_4h", ""),
        "bias_1h":         form.get("bias_1h", ""),
        "entry_price":     float(form.get("entry_price") or 0),
        "sl_price":        float(form.get("sl_price") or 0),
        "tp_price":        float(form.get("tp_price") or 0),
        "lot_size":        float(form.get("lot_size") or 0),
        "checklist_score": int(form.get("checklist_score") or 0),
        "setup_rating":    int(form.get("setup_rating") or 0),
        "emotion":         form.get("emotion", ""),
        "notes":           form.get("notes", ""),
    }


def build_edit_trade_data(form, user_id: int) -> dict:
    """Extract edit-trade data from a Flask form, auto-calculating PnL/RR."""
    exit_raw = form.get("exit_price", "").strip()
    result_raw = form.get("result", "").strip().upper() or None

    entry = float(form.get("entry_price") or 0)
    sl = float(form.get("sl_price") or 0)
    lot_size = float(form.get("lot_size") or 0)
    direction = form.get("direction", "LONG")

    if exit_raw and result_raw:
        exit_price = float(exit_raw)
        pnl, rr = calc_pnl_rr(entry, exit_price, sl, lot_size, direction)
        if result_raw == "BE":
            pnl = 0.0
    else:
        exit_price = float(exit_raw) if exit_raw else None
        pnl = float(form.get("pnl") or 0)
        rr = float(form.get("rr_achieved") or 0)

    return {
        "user_id":         user_id,
        "date":            form.get("date", date.today().isoformat()),
        "time":            form.get("time", "00:00"),
        "direction":       direction,
        "bias_4h":         form.get("bias_4h", ""),
        "bias_1h":         form.get("bias_1h", ""),
        "entry_price":     entry,
        "sl_price":        sl,
        "tp_price":        float(form.get("tp_price") or 0),
        "lot_size":        lot_size,
        "exit_price":      exit_price,
        "result":          result_raw,
        "pnl":             pnl,
        "rr_achieved":     rr,
        "checklist_score": int(form.get("checklist_score") or 0),
        "setup_rating":    int(form.get("setup_rating") or 3),
        "emotion":         form.get("emotion", ""),
        "notes":           form.get("notes", ""),
    }
