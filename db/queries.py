# db/queries.py — all SQL in one place, returns plain dicts
from datetime import date as _date
from db.models import get_conn


# ── Trades ────────────────────────────────────────────────────────────────────

def insert_trade(data: dict) -> int:
    sql = """
    INSERT INTO trades
        (date, time, direction, bias_4h, bias_1h,
         entry_price, sl_price, tp_price, lot_size,
         checklist_score, setup_rating, emotion, notes)
    VALUES
        (:date, :time, :direction, :bias_4h, :bias_1h,
         :entry_price, :sl_price, :tp_price, :lot_size,
         :checklist_score, :setup_rating, :emotion, :notes)
    """
    with get_conn() as conn:
        cur = conn.execute(sql, data)
        return cur.lastrowid


def update_trade_result(trade_id: int, exit_price: float, result: str, pnl: float, rr: float):
    sql = """
    UPDATE trades
    SET exit_price=?, result=?, pnl=?, rr_achieved=?
    WHERE id=?
    """
    with get_conn() as conn:
        conn.execute(sql, (exit_price, result, pnl, rr, trade_id))


def get_all_trades(limit: int = 50, offset: int = 0) -> list[dict]:
    sql = "SELECT * FROM trades ORDER BY date DESC, time DESC LIMIT ? OFFSET ?"
    with get_conn() as conn:
        rows = conn.execute(sql, (limit, offset)).fetchall()
    return [dict(r) for r in rows]


def get_trade(trade_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    return dict(row) if row else None


def get_trades_by_date(date_str: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE date=? ORDER BY time", (date_str,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Sessions ──────────────────────────────────────────────────────────────────

def get_or_create_session(date_str: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE date=?", (date_str,)
        ).fetchone()
        if not row:
            conn.execute("INSERT INTO sessions (date) VALUES (?)", (date_str,))
            row = conn.execute(
                "SELECT * FROM sessions WHERE date=?", (date_str,)
            ).fetchone()
    return dict(row)


def increment_session(date_str: str, is_loss: bool, pnl: float):
    loss_inc = 1 if is_loss else 0
    with get_conn() as conn:
        conn.execute("""
        UPDATE sessions
        SET trades_taken = trades_taken + 1,
            losses_taken = losses_taken + ?,
            daily_pnl    = daily_pnl + ?
        WHERE date = ?
        """, (loss_inc, pnl, date_str))


def set_session_status(date_str: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET status=? WHERE date=?", (status, date_str)
        )


# ── Account ───────────────────────────────────────────────────────────────────

def upsert_balance(date_str: str, balance: float, note: str = ""):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO account (date, balance, note) VALUES (?,?,?)
        ON CONFLICT(date) DO UPDATE SET balance=excluded.balance, note=excluded.note
        """, (date_str, balance, note))


def get_balance_history(days: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM account ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Stats (used by performance page) ─────────────────────────────────────────

def get_stats_summary() -> dict:
    sql = """
    SELECT
        COUNT(*)                                     AS total,
        SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
        ROUND(AVG(CASE WHEN result IN ('WIN','LOSS') THEN rr_achieved END), 2) AS avg_rr,
        ROUND(SUM(pnl), 2)                           AS total_pnl
    FROM trades
    WHERE result IS NOT NULL
    """
    with get_conn() as conn:
        row = conn.execute(sql).fetchone()
    d = dict(row)
    d["win_rate"] = round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0
    return d
