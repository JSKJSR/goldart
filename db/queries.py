# db/queries.py — all SQL in one place, returns plain dicts
# Uses psycopg2 with RealDictCursor so rows behave like dicts (same API as before).
# Placeholders: %s (positional) or %(name)s (named dict) — NOT SQLite's ?/:name.

from contextlib import contextmanager
import psycopg2.extras
from db.models import get_conn


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


# ── Trades ────────────────────────────────────────────────────────────────────

def insert_trade(data: dict) -> int:
    sql = """
    INSERT INTO trades
        (date, time, direction, bias_4h, bias_1h,
         entry_price, sl_price, tp_price, lot_size,
         checklist_score, setup_rating, emotion, notes)
    VALUES
        (%(date)s, %(time)s, %(direction)s, %(bias_4h)s, %(bias_1h)s,
         %(entry_price)s, %(sl_price)s, %(tp_price)s, %(lot_size)s,
         %(checklist_score)s, %(setup_rating)s, %(emotion)s, %(notes)s)
    RETURNING id
    """
    with _db() as cur:
        cur.execute(sql, data)
        return cur.fetchone()["id"]


def update_trade_result(trade_id: int, exit_price: float, result: str, pnl: float, rr: float):
    sql = """
    UPDATE trades
    SET exit_price=%s, result=%s, pnl=%s, rr_achieved=%s
    WHERE id=%s
    """
    with _db() as cur:
        cur.execute(sql, (exit_price, result, pnl, rr, trade_id))


def get_all_trades(limit: int = 50, offset: int = 0) -> list[dict]:
    sql = "SELECT * FROM trades ORDER BY date DESC, time DESC LIMIT %s OFFSET %s"
    with _db() as cur:
        cur.execute(sql, (limit, offset))
        return [dict(r) for r in cur.fetchall()]


def get_trade(trade_id: int) -> dict | None:
    with _db() as cur:
        cur.execute("SELECT * FROM trades WHERE id=%s", (trade_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_trades_by_date(date_str: str) -> list[dict]:
    with _db() as cur:
        cur.execute(
            "SELECT * FROM trades WHERE date=%s ORDER BY time", (date_str,)
        )
        return [dict(r) for r in cur.fetchall()]


# ── Sessions ──────────────────────────────────────────────────────────────────

def get_or_create_session(date_str: str) -> dict:
    with _db() as cur:
        cur.execute("SELECT * FROM sessions WHERE date=%s", (date_str,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO sessions (date) VALUES (%s)", (date_str,))
            cur.execute("SELECT * FROM sessions WHERE date=%s", (date_str,))
            row = cur.fetchone()
    return dict(row)


def increment_session(date_str: str, is_loss: bool, pnl: float):
    loss_inc = 1 if is_loss else 0
    with _db() as cur:
        cur.execute("""
        UPDATE sessions
        SET trades_taken = trades_taken + 1,
            losses_taken = losses_taken + %s,
            daily_pnl    = daily_pnl + %s
        WHERE date = %s
        """, (loss_inc, pnl, date_str))


def set_session_status(date_str: str, status: str):
    with _db() as cur:
        cur.execute(
            "UPDATE sessions SET status=%s WHERE date=%s", (status, date_str)
        )


# ── Account ───────────────────────────────────────────────────────────────────

def upsert_balance(date_str: str, balance: float, note: str = ""):
    with _db() as cur:
        cur.execute("""
        INSERT INTO account (date, balance, note) VALUES (%s, %s, %s)
        ON CONFLICT (date) DO UPDATE SET balance=EXCLUDED.balance, note=EXCLUDED.note
        """, (date_str, balance, note))


def get_balance_history(days: int = 30) -> list[dict]:
    with _db() as cur:
        cur.execute(
            "SELECT * FROM account ORDER BY date DESC LIMIT %s", (days,)
        )
        return [dict(r) for r in cur.fetchall()]


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats_summary() -> dict:
    sql = """
    SELECT
        COUNT(*)                                          AS total,
        SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END)   AS wins,
        SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END)   AS losses,
        ROUND(AVG(CASE WHEN result IN ('WIN','LOSS')
                       THEN rr_achieved END)::numeric, 2) AS avg_rr,
        ROUND(SUM(pnl)::numeric, 2)                       AS total_pnl
    FROM trades
    WHERE result IS NOT NULL
    """
    with _db() as cur:
        cur.execute(sql)
        d = dict(cur.fetchone())
    d["wins"]     = int(d["wins"]   or 0)
    d["losses"]   = int(d["losses"] or 0)
    d["total"]    = int(d["total"]  or 0)
    d["win_rate"] = round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0
    return d
