# core/signals.py — combines indicators into a tradeable signal
#
# Timeframe responsibilities:
#   4H  → Primary trend + Major S/R + Fibonacci swing
#   1H  → Confirmation trend + Minor S/R
#   15M → EMA 15/21 touch + signal candle (entry timeframe)
from __future__ import annotations  # enables PEP 604 (X | Y) on Python 3.9

import pandas as pd
from goldart.services.indicators import (
    ema_values, detect_trend, detect_sr_levels,
    fib_levels, auto_swing
)

# ── Touch thresholds (% of price) ────────────────────────────────────────────
EMA_TOUCH_PCT = 0.0015   # 0.15% — price within this % of EMA = "touching"
FIB_TOUCH_PCT = 0.0020   # 0.20%
SR_TOUCH_PCT  = 0.0030   # 0.30%


def _near(price: float, level: float, pct: float) -> bool:
    return abs(price - level) / price <= pct


def _nearest_sr(price: float, levels: list) -> float | None:
    """Returns the closest S/R level to price, or None."""
    if not levels:
        return None
    return min(levels, key=lambda x: abs(x - price))


def analyse(df_1h: pd.DataFrame, df_4h: pd.DataFrame, df_15m: pd.DataFrame) -> dict:
    """
    Full multi-timeframe analysis snapshot.

    df_4h  → trend bias + major S/R + fibonacci
    df_1h  → trend confirmation + minor S/R
    df_15m → EMA 15/21 + entry candle signal
    """
    current_price = float(df_15m["close"].iloc[-1])

    # ── Trend (4H primary, 1H confirmation) ──────────────────────────────────
    trend_4h = detect_trend(df_4h, window=3, swing_count=3)
    trend_1h = detect_trend(df_1h, window=3, swing_count=3)
    aligned  = (trend_4h == trend_1h) and (trend_4h != "RANGING")

    # ── EMA on 15M (entry timeframe) ─────────────────────────────────────────
    ema_15m = ema_values(df_15m)
    at_ema15 = _near(current_price, ema_15m["ema15"], EMA_TOUCH_PCT)
    at_ema21 = _near(current_price, ema_15m["ema21"], EMA_TOUCH_PCT)

    # ── Major S/R on 4H ──────────────────────────────────────────────────────
    sr_major = detect_sr_levels(df_4h, window=5, max_levels=3, zone_pct=0.005)
    at_major_support    = any(_near(current_price, l, SR_TOUCH_PCT) for l in sr_major["support"])
    at_major_resistance = any(_near(current_price, l, SR_TOUCH_PCT) for l in sr_major["resistance"])
    nearest_major       = _nearest_sr(current_price, sr_major["support"] + sr_major["resistance"])

    # ── Minor S/R on 1H ──────────────────────────────────────────────────────
    sr_minor = detect_sr_levels(df_1h, window=3, max_levels=4, zone_pct=0.004)
    at_minor_support    = any(_near(current_price, l, SR_TOUCH_PCT) for l in sr_minor["support"])
    at_minor_resistance = any(_near(current_price, l, SR_TOUCH_PCT) for l in sr_minor["resistance"])

    at_sr = at_major_support or at_major_resistance or at_minor_support or at_minor_resistance

    # ── Fibonacci (4H true swing) ─────────────────────────────────────────────
    swing_high, swing_low = auto_swing(df_4h, window=3)
    fibs    = fib_levels(swing_high, swing_low)
    fib_618 = fibs["0.618"]
    at_fib618 = _near(current_price, fib_618, FIB_TOUCH_PCT)

    # ── Signal candle (15M entry candle) ─────────────────────────────────────
    last        = df_15m.iloc[-1]
    bull_candle = float(last["close"]) > float(last["open"])
    bear_candle = float(last["close"]) < float(last["open"])

    # candle body size as % of range — filters doji/indecision
    candle_range = float(last["high"]) - float(last["low"])
    candle_body  = abs(float(last["close"]) - float(last["open"]))
    strong_candle = (candle_body / candle_range) > 0.4 if candle_range > 0 else False

    valid_bull_signal = bull_candle and strong_candle and trend_4h == "BULLISH"
    valid_bear_signal = bear_candle and strong_candle and trend_4h == "BEARISH"

    # ── Score (max 5) ─────────────────────────────────────────────────────────
    score = sum([
        aligned,                              # Both TFs agree
        at_ema21 or at_ema15,                 # Price at EMA on 15M
        at_fib618,                            # Fib 0.618 confluence
        at_major_support or at_major_resistance,  # Major 4H S/R
        valid_bull_signal or valid_bear_signal,   # Clean signal candle
    ])

    signal_active = score >= 3

    return {
        # Price
        "current_price":   round(current_price, 2),

        # Trend
        "trend_4h":        trend_4h,
        "trend_1h":        trend_1h,
        "aligned":         aligned,

        # EMA (15M)
        "ema":             ema_15m,
        "at_ema15":        at_ema15,
        "at_ema21":        at_ema21,

        # S/R — split by timeframe
        "sr_major":        sr_major,          # 4H levels
        "sr_minor":        sr_minor,          # 1H levels
        "at_sr":           at_sr,
        "nearest_major":   nearest_major,

        # Fibonacci (4H swing)
        "fibs":            fibs,
        "fib_618":         fib_618,
        "at_fib618":       at_fib618,
        "swing_high":      round(swing_high, 2),
        "swing_low":       round(swing_low,  2),

        # Candle (15M)
        "bull_candle":     bull_candle,
        "bear_candle":     bear_candle,
        "strong_candle":   strong_candle,
        "valid_signal":    valid_bull_signal or valid_bear_signal,

        # Summary
        "score":           score,
        "signal_active":   signal_active,
    }
