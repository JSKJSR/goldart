# db/models.py — schema only, no business logic
import sqlite3
from config import DB_PATH

DDL = """
CREATE TABLE IF NOT EXISTS trades (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             TEXT    NOT NULL,
    time             TEXT    NOT NULL,
    direction        TEXT    NOT NULL,         -- LONG | SHORT
    bias_4h          TEXT,                     -- BULLISH | BEARISH | RANGING
    bias_1h          TEXT,
    entry_price      REAL    NOT NULL,
    sl_price         REAL    NOT NULL,
    tp_price         REAL    NOT NULL,
    lot_size         REAL,
    exit_price       REAL,
    result           TEXT,                     -- WIN | LOSS | BE | OPEN
    pnl              REAL    DEFAULT 0,
    rr_achieved      REAL    DEFAULT 0,
    checklist_score  INTEGER DEFAULT 0,
    setup_rating     INTEGER DEFAULT 0,        -- 1-5
    emotion          TEXT,
    notes            TEXT,
    screenshot_path  TEXT,
    created_at       TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT    UNIQUE NOT NULL,
    trades_taken   INTEGER DEFAULT 0,
    losses_taken   INTEGER DEFAULT 0,
    daily_pnl      REAL    DEFAULT 0,
    status         TEXT    DEFAULT 'ACTIVE'   -- ACTIVE | CLOSED | MAX_LOSS | MAX_TRADES
);

CREATE TABLE IF NOT EXISTS account (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    UNIQUE NOT NULL,
    balance     REAL    NOT NULL,
    note        TEXT
);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript(DDL)
