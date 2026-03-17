# db/queries.py — all SQL in one place, returns plain dicts
# Uses psycopg2 with RealDictCursor so rows behave like dicts (same API as before).
# Placeholders: %s (positional) or %(name)s (named dict) — NOT SQLite's ?/:name.
from __future__ import annotations  # enables PEP 604 (X | Y) on Python 3.9

from contextlib import contextmanager
import psycopg2.extras
from goldart.database.models import get_conn


@contextmanager
def _db():
    """
    Yields a RealDictCursor inside a managed transaction.
    Auto-commits on clean exit, rolls back on exception, always closes connection.
    """
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username: str, email: str, password_hash: str) -> int:
    sql = """
    INSERT INTO users (username, email, password_hash)
    VALUES (%s, %s, %s) RETURNING id
    """
    with _db() as cur:
        cur.execute(sql, (username, email, password_hash))
        return cur.fetchone()["id"]


def get_user_by_username(username: str) -> dict | None:
    with _db() as cur:
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    with _db() as cur:
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        row = cur.fetchone()
    return dict(row) if row else None


# ── Trades ────────────────────────────────────────────────────────────────────

def insert_trade(data: dict) -> int:
    sql = """
    INSERT INTO trades
        (user_id, date, time, direction, bias_4h, bias_1h,
         entry_price, sl_price, tp_price, lot_size,
         checklist_score, setup_rating, emotion, notes)
    VALUES
        (%(user_id)s, %(date)s, %(time)s, %(direction)s, %(bias_4h)s, %(bias_1h)s,
         %(entry_price)s, %(sl_price)s, %(tp_price)s, %(lot_size)s,
         %(checklist_score)s, %(setup_rating)s, %(emotion)s, %(notes)s)
    RETURNING id
    """
    with _db() as cur:
        cur.execute(sql, data)
        return cur.fetchone()["id"]


def update_trade_result(trade_id: int, exit_price: float, result: str,
                        pnl: float, rr: float, user_id: int):
    sql = """
    UPDATE trades
    SET exit_price=%s, result=%s, pnl=%s, rr_achieved=%s
    WHERE id=%s AND user_id=%s
    """
    with _db() as cur:
        cur.execute(sql, (exit_price, result, pnl, rr, trade_id, user_id))


def update_trade_full(trade_id: int, data: dict):
    """Full edit — updates every user-editable field on a trade row."""
    sql = """
    UPDATE trades SET
        date=%(date)s, time=%(time)s, direction=%(direction)s,
        bias_4h=%(bias_4h)s, bias_1h=%(bias_1h)s,
        entry_price=%(entry_price)s, sl_price=%(sl_price)s, tp_price=%(tp_price)s,
        lot_size=%(lot_size)s, exit_price=%(exit_price)s,
        result=%(result)s, pnl=%(pnl)s, rr_achieved=%(rr_achieved)s,
        checklist_score=%(checklist_score)s, setup_rating=%(setup_rating)s,
        emotion=%(emotion)s, notes=%(notes)s
    WHERE id=%(id)s AND user_id=%(user_id)s
    """
    data["id"] = trade_id
    with _db() as cur:
        cur.execute(sql, data)


def delete_trade(trade_id: int, user_id: int):
    with _db() as cur:
        cur.execute("DELETE FROM trades WHERE id=%s AND user_id=%s",
                    (trade_id, user_id))


def get_all_trades(user_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    sql = """
    SELECT * FROM trades WHERE user_id=%s
    ORDER BY date DESC, time DESC LIMIT %s OFFSET %s
    """
    with _db() as cur:
        cur.execute(sql, (user_id, limit, offset))
        return [dict(r) for r in cur.fetchall()]


def get_trade(trade_id: int, user_id: int) -> dict | None:
    with _db() as cur:
        cur.execute("SELECT * FROM trades WHERE id=%s AND user_id=%s",
                    (trade_id, user_id))
        row = cur.fetchone()
    return dict(row) if row else None


def get_trades_by_date(date_str: str, user_id: int) -> list[dict]:
    with _db() as cur:
        cur.execute(
            "SELECT * FROM trades WHERE date=%s AND user_id=%s ORDER BY time",
            (date_str, user_id),
        )
        return [dict(r) for r in cur.fetchall()]


# ── Sessions ──────────────────────────────────────────────────────────────────

def get_or_create_session(date_str: str, user_id: int) -> dict:
    with _db() as cur:
        cur.execute("SELECT * FROM sessions WHERE date=%s AND user_id=%s",
                    (date_str, user_id))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO sessions (date, user_id) VALUES (%s, %s)",
                (date_str, user_id),
            )
            cur.execute("SELECT * FROM sessions WHERE date=%s AND user_id=%s",
                        (date_str, user_id))
            row = cur.fetchone()
    return dict(row)


def increment_session(date_str: str, user_id: int, is_loss: bool, pnl: float):
    loss_inc = 1 if is_loss else 0
    with _db() as cur:
        cur.execute("""
        UPDATE sessions
        SET trades_taken = trades_taken + 1,
            losses_taken = losses_taken + %s,
            daily_pnl    = daily_pnl + %s
        WHERE date = %s AND user_id = %s
        """, (loss_inc, pnl, date_str, user_id))


def set_session_status(date_str: str, user_id: int, status: str):
    with _db() as cur:
        cur.execute(
            "UPDATE sessions SET status=%s WHERE date=%s AND user_id=%s",
            (status, date_str, user_id),
        )


# ── Account ───────────────────────────────────────────────────────────────────

def upsert_balance(date_str: str, user_id: int, balance: float, note: str = ""):
    with _db() as cur:
        cur.execute("""
        INSERT INTO account (date, user_id, balance, note) VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, date)
        DO UPDATE SET balance=EXCLUDED.balance, note=EXCLUDED.note
        """, (date_str, user_id, balance, note))


def get_balance_history(user_id: int, days: int = 30) -> list[dict]:
    with _db() as cur:
        cur.execute(
            "SELECT * FROM account WHERE user_id=%s ORDER BY date DESC LIMIT %s",
            (user_id, days),
        )
        return [dict(r) for r in cur.fetchall()]


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats_summary(user_id: int) -> dict:
    sql = """
    SELECT
        COUNT(*)                                          AS total,
        SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END)   AS wins,
        SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END)   AS losses,
        ROUND(AVG(CASE WHEN result IN ('WIN','LOSS')
                       THEN rr_achieved END)::numeric, 2) AS avg_rr,
        ROUND(SUM(pnl)::numeric, 2)                       AS total_pnl
    FROM trades
    WHERE result IS NOT NULL AND user_id = %s
    """
    with _db() as cur:
        cur.execute(sql, (user_id,))
        d = dict(cur.fetchone())
    d["wins"]      = int(d["wins"]   or 0)
    d["losses"]    = int(d["losses"] or 0)
    d["total"]     = int(d["total"]  or 0)
    d["avg_rr"]    = float(d["avg_rr"]    or 0)
    d["total_pnl"] = float(d["total_pnl"] or 0)
    d["win_rate"]  = round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0
    return d
