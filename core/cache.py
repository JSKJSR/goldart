# core/cache.py — simple in-memory TTL cache
# Swap this module to use Redis or filesystem cache without touching routes

import time

_store: dict = {}   # { key: {"data": ..., "ts": float} }

TTL_SECONDS = 60    # match Twelve Data free-tier window (8 credits/min)


def get(key: str):
    """Return cached value if fresh, else None."""
    entry = _store.get(key)
    if entry and (time.time() - entry["ts"]) < TTL_SECONDS:
        return entry["data"]
    return None


def set(key: str, data):
    """Store data with current timestamp."""
    _store[key] = {"data": data, "ts": time.time()}


def age(key: str) -> int:
    """Seconds since last cache write, or -1 if not cached."""
    entry = _store.get(key)
    if not entry:
        return -1
    return int(time.time() - entry["ts"])


def remaining(key: str) -> int:
    """Seconds until cache expires, or 0 if already expired."""
    a = age(key)
    return max(TTL_SECONDS - a, 0) if a >= 0 else 0
