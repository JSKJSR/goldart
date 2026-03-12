# core/indicators.py — pure functions, DataFrame in → values out
# Replace any function independently without touching other modules
#
# EMA uses pure pandas ewm() — identical to pandas-ta's ta.ema() formula,
# without the heavy numba/LLVM dependency that crashes on serverless runtimes.
from __future__ import annotations  # enables PEP 604 (X | Y) on Python 3.9

import pandas as pd


# ── EMA ───────────────────────────────────────────────────────────────────────
# Always pass 15M DataFrame here — EMA is an entry-timeframe tool

def ema(df: pd.DataFrame, period: int) -> pd.Series:
    """Exponential Moving Average — mathematically identical to pandas-ta ta.ema()."""
    return df["close"].ewm(span=period, adjust=False).mean()


def ema_values(df: pd.DataFrame) -> dict:
    """Latest EMA 15 and EMA 21 from a 15M DataFrame."""
    return {
        "ema15": round(float(ema(df, 15).iloc[-1]), 2),
        "ema21": round(float(ema(df, 21).iloc[-1]), 2),
    }


# ── Swing Detection ───────────────────────────────────────────────────────────
# True pivot detection: candle must be the highest/lowest in window on BOTH sides

def _find_swings(df: pd.DataFrame, window: int = 3) -> tuple[list, list]:
    """
    Returns (swing_highs, swing_lows) as lists of (price, datetime) tuples.
    Scans newest → oldest so index 0 = most recent swing.
    """
    highs = df["high"]
    lows  = df["low"]
    swing_highs, swing_lows = [], []

    for i in range(len(df) - 1 - window, window - 1, -1):
        window_slice_h = highs.iloc[i - window : i + window + 1]
        window_slice_l = lows.iloc[i  - window : i + window + 1]

        if highs.iloc[i] == window_slice_h.max():
            swing_highs.append((round(float(highs.iloc[i]), 2), df.index[i]))

        if lows.iloc[i] == window_slice_l.min():
            swing_lows.append((round(float(lows.iloc[i]), 2), df.index[i]))

    return swing_highs, swing_lows


def last_swing_high(df: pd.DataFrame, window: int = 3) -> float | None:
    """Most recent confirmed swing high price."""
    highs, _ = _find_swings(df, window)
    return highs[0][0] if highs else None


def last_swing_low(df: pd.DataFrame, window: int = 3) -> float | None:
    """Most recent confirmed swing low price."""
    _, lows = _find_swings(df, window)
    return lows[0][0] if lows else None


# ── Trend ─────────────────────────────────────────────────────────────────────
# Multi-swing structure: requires 3 consecutive HH+HL or LH+LL

def detect_trend(df: pd.DataFrame, window: int = 3, swing_count: int = 3) -> str:
    """
    Proper market structure trend detection.
    Looks at the last `swing_count` swing highs and lows.

    BULLISH  = each successive swing high AND swing low is higher than the previous
    BEARISH  = each successive swing high AND swing low is lower than the previous
    RANGING  = mixed / not enough swings

    Returns: BULLISH | BEARISH | RANGING
    """
    swing_highs, swing_lows = _find_swings(df, window)

    if len(swing_highs) < swing_count or len(swing_lows) < swing_count:
        return "RANGING"

    # Most recent first → check if each is higher/lower than the next
    recent_highs = [sh[0] for sh in swing_highs[:swing_count]]
    recent_lows  = [sl[0] for sl in swing_lows[:swing_count]]

    hh = all(recent_highs[i] > recent_highs[i + 1] for i in range(swing_count - 1))
    hl = all(recent_lows[i]  > recent_lows[i + 1]  for i in range(swing_count - 1))
    lh = all(recent_highs[i] < recent_highs[i + 1] for i in range(swing_count - 1))
    ll = all(recent_lows[i]  < recent_lows[i + 1]  for i in range(swing_count - 1))

    if hh and hl:
        return "BULLISH"
    if lh and ll:
        return "BEARISH"
    return "RANGING"


# ── Support / Resistance ──────────────────────────────────────────────────────
# Dual-timeframe: pass 4H df for major levels, 1H df for minor levels

def detect_sr_levels(
    df: pd.DataFrame,
    window: int = 5,
    max_levels: int = 4,
    zone_pct: float = 0.004,   # merge levels within 0.4% of each other
) -> dict:
    """
    Swing-pivot S/R detection.

    window:    candles each side required to confirm pivot (5 = stronger levels)
    zone_pct:  merge threshold — levels this close are treated as one zone
    max_levels: max levels returned per side

    Returns: {"resistance": [price, ...], "support": [price, ...]}
    """
    swing_highs, swing_lows = _find_swings(df, window)

    resistances = [sh[0] for sh in swing_highs]
    supports    = [sl[0] for sl in swing_lows]

    def merge_zones(levels: list, reverse: bool = True) -> list:
        """Merge levels within zone_pct of each other, keep strongest (most touched)."""
        if not levels:
            return []
        unique, prev = [], None
        for lvl in sorted(levels, reverse=reverse):
            if prev is None or abs(lvl - prev) / prev > zone_pct:
                unique.append(lvl)
                prev = lvl
        return unique[:max_levels]

    return {
        "resistance": merge_zones(resistances, reverse=True),
        "support":    merge_zones(supports,    reverse=False),
    }


# ── Fibonacci ─────────────────────────────────────────────────────────────────
# Uses true swing high/low, not absolute max/min

FIB_RATIOS = {
    "0.236": 0.236,
    "0.382": 0.382,
    "0.500": 0.500,
    "0.618": 0.618,   # ← key level
    "0.786": 0.786,
}


def fib_levels(swing_high: float, swing_low: float) -> dict:
    """
    Fibonacci retracement levels.
    Bullish move:  drew from swing_low → swing_high, price retraces down
    Bearish move:  drew from swing_high → swing_low, price retraces up
    """
    diff = swing_high - swing_low
    return {
        label: round(swing_high - ratio * diff, 2)
        for label, ratio in FIB_RATIOS.items()
    }


def auto_swing(df: pd.DataFrame, window: int = 3) -> tuple[float, float]:
    """
    Returns (last_swing_high, last_swing_low) from true pivot detection.
    Falls back to 50-candle max/min if not enough swings found.
    """
    sh = last_swing_high(df, window)
    sl = last_swing_low(df, window)

    # Fallback: not enough structure yet
    if sh is None:
        sh = float(df["high"].tail(50).max())
    if sl is None:
        sl = float(df["low"].tail(50).min())

    return sh, sl
