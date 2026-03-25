# db/models.py — schema only, no business logic
# Database: Supabase PostgreSQL (psycopg2-binary)
# Swap get_conn() here to change the backend without touching queries.

import logging
import psycopg2
import psycopg2.extras
import psycopg2.pool
from goldart.config import DATABASE_URL

log = logging.getLogger(__name__)

# ── Connection pool ──────────────────────────────────────────────────────────
_pool = None


def _get_pool():
    """Lazy-init a connection pool (1–5 connections)."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.SimpleConnectionPool(1, 5, DATABASE_URL)
    return _pool


def get_conn():
    """Get a connection from the pool. Caller must return via put_conn()."""
    try:
        return _get_pool().getconn()
    except Exception:
        # Pool exhausted or stale — reset and retry once
        global _pool
        if _pool and not _pool.closed:
            _pool.closeall()
        _pool = None
        return _get_pool().getconn()


def put_conn(conn):
    """Return a connection to the pool."""
    try:
        _get_pool().putconn(conn)
    except Exception:
        # If pool was reset, just close the orphan
        try:
            conn.close()
        except Exception:
            pass


# ── DDL — one statement per table ─────────────────────────────────────────────
_DDL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id             SERIAL PRIMARY KEY,
        username       VARCHAR(50)  UNIQUE NOT NULL,
        email          VARCHAR(255) UNIQUE NOT NULL,
        password_hash  TEXT         NOT NULL,
        created_at     TIMESTAMPTZ  DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        id               SERIAL PRIMARY KEY,
        user_id          INTEGER REFERENCES users(id),
        date             TEXT    NOT NULL,
        time             TEXT    NOT NULL,
        direction        TEXT    NOT NULL,
        bias_4h          TEXT,
        bias_1h          TEXT,
        entry_price      REAL    NOT NULL,
        sl_price         REAL    NOT NULL,
        tp_price         REAL    NOT NULL,
        lot_size         REAL,
        exit_price       REAL,
        result           TEXT,
        pnl              REAL    DEFAULT 0,
        rr_achieved      REAL    DEFAULT 0,
        checklist_score  INTEGER DEFAULT 0,
        setup_rating     INTEGER DEFAULT 0,
        emotion          TEXT,
        notes            TEXT,
        screenshot_path  TEXT,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER REFERENCES users(id),
        date           TEXT    NOT NULL,
        trades_taken   INTEGER DEFAULT 0,
        losses_taken   INTEGER DEFAULT 0,
        daily_pnl      REAL    DEFAULT 0,
        status         TEXT    DEFAULT 'ACTIVE'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS account (
        id      SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        date    TEXT    NOT NULL,
        balance REAL    NOT NULL,
        note    TEXT
    )
    """,
]

# ── Migrations — add user_id to existing tables (idempotent) ─────────────────
_MIGRATIONS = [
    "ALTER TABLE trades   ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE account  ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    # Replace old single-user unique constraints with multi-user compound indexes
    "ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_date_key",
    "CREATE UNIQUE INDEX IF NOT EXISTS sessions_user_date_idx ON sessions (user_id, date)",
    "ALTER TABLE account DROP CONSTRAINT IF EXISTS account_date_key",
    "CREATE UNIQUE INDEX IF NOT EXISTS account_user_date_idx ON account (user_id, date)",
]


def init_db():
    """Create tables if they don't exist, then run migrations. Safe to call on every startup."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for stmt in _DDL:
                cur.execute(stmt)
            for stmt in _MIGRATIONS:
                cur.execute(stmt)
        conn.commit()
    finally:
        put_conn(conn)
