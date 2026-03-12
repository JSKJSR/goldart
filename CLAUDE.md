# Goldart — XAU/USD Trading Analysis & Journal

Flask web app for gold trading: multi-timeframe signal analysis (4H/1H/15M),
risk/lot-size calculator, and a PostgreSQL-backed trade journal.
Deployed on Vercel (serverless) with Supabase as the database.

---

## Commands

```bash
python app.py           # dev server → http://localhost:8080 (debug=True)
```

No test runner or linter is configured yet. Before adding one, check requirements.txt first.

---

## Tech Stack

- **Python 3.9+** — use `from __future__ import annotations` in all core/ files
- **Flask 3** — Blueprints only; no logic in routes, only call core/ functions
- **Supabase PostgreSQL** — psycopg2-binary; connection via DATABASE_URL in .env
- **Twelve Data API** — OHLCV for XAU/USD; 8 credits/min on free tier
- **Pandas** — DataFrames for OHLCV; do not import pandas-ta (breaks serverless)
- **Vercel** — entry: `api/index.py`; all routes must work as a single lambda

---

## Architecture

```
app.py              ← thin entry point: wires Flask + blueprints, nothing else
config.py           ← single source of truth for ALL settings (read from .env)
core/
  data.py           ← fetch OHLCV from Twelve Data (swap here to change provider)
  indicators.py     ← pure functions: EMA, swing detection, trend, S/R, Fibonacci
  signals.py        ← combines indicators → tradeable signal dict + score (0–5)
  risk.py           ← position sizing: lot size, TP, RR for XAU/USD
  session.py        ← enforces daily limits (MAX_TRADES, MAX_LOSSES)
  cache.py          ← in-memory TTL cache (60s); swap to Redis without touching routes
routes/
  dashboard.py      ← / (home)
  analysis.py       ← /analysis  (signal snapshot + risk calculator)
  trades.py         ← /trades    (journal CRUD, close/edit trades)
  export.py         ← /export    (Excel + PDF download)
db/
  models.py         ← schema DDL + get_conn(); swap DB backend here
  queries.py        ← all SQL; no raw SQL anywhere else
templates/          ← Jinja2 HTML
static/             ← CSS, JS, images
api/index.py        ← Vercel serverless entry (wraps create_app())
```

---

## Key Rules

**Never touch these without reading the surrounding code first:**
- `db/models.py` — changing schema requires a manual Supabase migration; there is no ORM
- `core/signals.py` — touch thresholds (`EMA_TOUCH_PCT`, `FIB_TOUCH_PCT`, `SR_TOUCH_PCT`) are tuned values
- `core/cache.py` — TTL is set to 60s to match Twelve Data free-tier (8 req/min); do not lower it
- `api/index.py` — Vercel lambda entry; keep this a thin wrapper

**Gold-specific constants (do not change without reason):**
```python
pip_value_per_lot = 100.0   # USD per lot per $1 XAU/USD price move
min_lot_size      = 0.01    # 1 micro lot
```

**Timeframe responsibilities:**
- `4H` → primary trend + major S/R + Fibonacci swing
- `1H` → trend confirmation + minor S/R
- `15M` → EMA 15/21 touch + signal candle (entry only)

**Signal score system (core/signals.py):**
- Score 0–5; `signal_active = True` when score ≥ 3
- Do not lower the threshold without a backtest reason

---

## Environment Variables

All settings come from `.env` (local) or Vercel Environment Variables (prod).
See `.env.example` for all keys. Never commit `.env`.

```
ACCOUNT_BALANCE      # default: 2000
RISK_PER_TRADE       # default: 50
REWARD_PER_TRADE     # default: 100
MAX_TRADES_PER_DAY   # default: 3
MAX_LOSSES_PER_DAY   # default: 2
TWELVE_DATA_API_KEY  # required — get from twelvedata.com
DATABASE_URL         # Supabase URI — URL-encode special chars in password
SECRET_KEY           # Flask session key
```

---

## Database

3 tables: `trades`, `sessions`, `account`. Schema in `db/models.py`.
`init_db()` is called at startup — it is idempotent (CREATE TABLE IF NOT EXISTS).
All SQL lives in `db/queries.py`. Write raw psycopg2 queries, not an ORM.
Use `psycopg2.extras.RealDictCursor` so rows return as dicts.

**NEVER write SQL outside `db/queries.py`.**

---

## API Credit Budget (Twelve Data free tier)

Each live snapshot call costs **3 credits** (4H + 1H + 15M).
The 60s in-memory cache (`core/cache.py`) prevents hitting the 8 req/min limit.
`/analysis/api/snapshot` uses the 15M last close for price — saving 1 extra credit.

---

## Adding Features — Quick Reference

| Task | Where to change |
|---|---|
| New indicator | `core/indicators.py` — pure function, DataFrame in → value out |
| Change signal logic | `core/signals.py` — update `analyse()` |
| New route / page | `routes/new_file.py` → register blueprint in `app.py` |
| New DB table | Add DDL to `db/models.py`, queries to `db/queries.py` |
| Change data provider | Rewrite `core/data.py` only — all other modules are untouched |
| New export format | `routes/export.py` |
| Change risk model | `core/risk.py` — update `calculate()` |

---

## Deployment (Vercel)

- Entry: `api/index.py` wraps `create_app()` as a WSGI lambda
- `vercel.json` routes all traffic (`/*`) to `api/index.py`
- Set all env vars in Vercel dashboard → Project Settings → Environment Variables
- `DATABASE_URL` must use `?sslmode=require`
- `maxLambdaSize: 50mb` is required for pandas + psycopg2

**NEVER use `pandas-ta` or any C-extension library that requires compilation** —
it will break the Vercel build. Use pure pandas (`ewm()`, `rolling()`, etc.) instead.
