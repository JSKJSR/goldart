# core/data.py — fetch OHLCV from Twelve Data; swap this file to change provider
import requests
import pandas as pd
from config import TWELVE_DATA_API_KEY, TWELVE_DATA_BASE, SYMBOL

# Candle count to fetch per request (enough for EMA 21 + S/R detection)
CANDLE_LIMIT = 100


class DataFetchError(Exception):
    pass


def fetch_ohlcv(timeframe: str = "1h") -> pd.DataFrame:
    """
    Returns a DataFrame with columns: [open, high, low, close, volume]
    Index: DatetimeIndex (UTC), newest last.

    timeframe examples: "1h", "4h", "15min"
    """
    if not TWELVE_DATA_API_KEY:
        raise DataFetchError("TWELVE_DATA_API_KEY not set in .env")

    params = {
        "symbol":     SYMBOL,
        "interval":   timeframe,
        "outputsize": CANDLE_LIMIT,
        "apikey":     TWELVE_DATA_API_KEY,
        "format":     "JSON",
    }

    resp = requests.get(f"{TWELVE_DATA_BASE}/time_series", params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") == "error":
        raise DataFetchError(payload.get("message", "Twelve Data error"))

    values = payload.get("values", [])
    if not values:
        raise DataFetchError("No candle data returned")

    df = pd.DataFrame(values)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime").sort_index()

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col])

    # Volume is not available for metals/forex on Twelve Data — keep only present columns
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    return df[cols]


def get_current_price() -> float:
    """Latest close price for XAU/USD."""
    if not TWELVE_DATA_API_KEY:
        raise DataFetchError("TWELVE_DATA_API_KEY not set in .env")

    params = {"symbol": SYMBOL, "apikey": TWELVE_DATA_API_KEY}
    resp = requests.get(f"{TWELVE_DATA_BASE}/price", params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()

    if "price" not in payload:
        raise DataFetchError(payload.get("message", "No price returned"))

    return float(payload["price"])
