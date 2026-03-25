# config.py — single source of truth for all settings
import os
from dotenv import load_dotenv

load_dotenv()

# --- Account ---
ACCOUNT_BALANCE   = float(os.getenv("ACCOUNT_BALANCE", 2000))
RISK_PER_TRADE    = float(os.getenv("RISK_PER_TRADE",  50))
REWARD_PER_TRADE  = float(os.getenv("REWARD_PER_TRADE", 100))

# --- Daily Limits ---
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", 3))
MAX_LOSSES_PER_DAY = int(os.getenv("MAX_LOSSES_PER_DAY", 2))

# --- Market ---
SYMBOL     = os.getenv("SYMBOL", "XAU/USD")
TIMEFRAMES = ["1h", "4h", "15min"]

# --- Twelve Data API ---
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")
TWELVE_DATA_BASE    = "https://api.twelvedata.com"

# --- AI Mentor ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MENTOR_MODEL      = os.getenv("MENTOR_MODEL", "claude-haiku-4-5-20241022")

# --- App ---
SECRET_KEY = os.getenv("SECRET_KEY", "goldart-dev-key")

# --- Database (Supabase PostgreSQL) ---
# Full DSN:  postgresql://user:password@host:port/dbname?sslmode=require
# Set this in .env locally and in Vercel Environment Variables for production.
DATABASE_URL = os.getenv("DATABASE_URL", "")
