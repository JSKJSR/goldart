# core/risk.py — position sizing for XAU/USD
# Gold: 1 standard lot = 100 oz. Pip = $0.01. 1 lot pip value ≈ $1.00 per $0.01 move
# At spot ~$2300: 1 lot moves $100 per $1 price move → pip_value_per_lot = $100 / $1

from goldart.config import RISK_PER_TRADE, REWARD_PER_TRADE


def calculate(entry: float, sl: float, direction: str) -> dict:
    """
    Returns lot size, TP price, and trade metrics for a $RISK_PER_TRADE risk.

    direction: "LONG" | "SHORT"
    """
    sl_distance = abs(entry - sl)           # in price units (e.g. $7.50)
    if sl_distance == 0:
        return {"error": "SL cannot equal entry price"}

    # Gold: pip value per lot = $100 per $1 move  → $10 per $0.10 move
    # 1 micro lot (0.01) = $1 per $1 move
    pip_value_per_lot = 100.0               # USD per lot per $1 gold move

    lot_size = round(RISK_PER_TRADE / (sl_distance * pip_value_per_lot), 2)
    lot_size = max(lot_size, 0.01)          # minimum 1 micro lot

    rr_ratio      = REWARD_PER_TRADE / RISK_PER_TRADE
    tp_distance   = sl_distance * rr_ratio

    if direction == "LONG":
        tp_price = round(entry + tp_distance, 2)
    else:
        tp_price = round(entry - tp_distance, 2)

    return {
        "entry":       round(entry, 2),
        "sl":          round(sl, 2),
        "tp":          round(tp_price, 2),
        "lot_size":    lot_size,
        "sl_distance": round(sl_distance, 2),
        "risk_usd":    RISK_PER_TRADE,
        "reward_usd":  REWARD_PER_TRADE,
        "rr_ratio":    rr_ratio,
    }
