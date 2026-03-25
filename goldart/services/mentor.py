"""AI Mentor — trade journal analysis via LLM (with rule-based fallback)."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import date

from goldart.database.queries import get_all_trades, get_stats_summary, get_current_streak

log = logging.getLogger(__name__)

# ── In-memory cache (24h TTL, keyed per user per day) ─────────────────────
_cache: dict[str, dict] = {}
_CACHE_TTL = 86400

_MIN_TRADES = 5


def _cache_key(user_id: int) -> str:
    return f"mentor:{user_id}:{date.today().isoformat()}"


# ── Main entry point ─────────────────────────────────────────────────────────

def get_mentor_analysis(user_id: int, force: bool = False) -> dict:
    """Analyze trades. Uses LLM if API key is set, otherwise rule-based."""
    stats = get_stats_summary(user_id)
    if stats["total"] < _MIN_TRADES:
        return {"error": f"Log at least {_MIN_TRADES} closed trades before requesting analysis. You have {stats['total']}."}

    # Check cache
    key = _cache_key(user_id)
    if not force and key in _cache:
        entry = _cache[key]
        if time.time() - entry["ts"] < _CACHE_TTL:
            return {
                "analysis": entry["text"],
                "cached": True,
                "generated_at": entry["time_str"],
                "mode": entry.get("mode", "unknown"),
            }

    streak = get_current_streak(user_id)
    trades = get_all_trades(user_id, limit=100)
    closed = [t for t in trades if t.get("result")]

    # Try LLM first, fall back to rule-based
    from goldart.config import ANTHROPIC_API_KEY, MENTOR_MODEL
    if ANTHROPIC_API_KEY:
        result = _llm_analysis(user_id, stats, streak, closed)
    else:
        result = _rule_based_analysis(stats, streak, closed)

    if "error" in result:
        return result

    # Cache the result
    now = time.time()
    time_str = time.strftime("%H:%M", time.localtime(now))
    _cache[key] = {"text": result["analysis"], "ts": now, "time_str": time_str, "mode": result["mode"]}

    result["cached"] = False
    result["generated_at"] = time_str
    return result


# ══════════════════════════════════════════════════════════════════════════════
# LLM ANALYSIS (Claude API)
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """\
You are an expert XAU/USD (gold) trading mentor reviewing a student's trade journal.
Be direct, specific, and actionable. Reference specific trades by date when making points.

Respond with these sections:

## Performance Summary
One paragraph overall assessment of their trading.

## Strengths
2-3 bullet points of what they're doing well, with specific trade date references.

## Areas to Improve
2-3 bullet points with specific, actionable advice grounded in their data.

## Pattern Analysis
Analyze these dimensions (skip any that lack data):
- Emotional patterns: do certain emotions correlate with losses?
- Setup quality: do higher checklist scores produce better results?
- Direction bias: are they better at longs or shorts?
- Bias alignment: are they trading against the higher-timeframe trend?

## Specific Trade Callouts
Call out 2-3 specific trades (by date) that illustrate key lessons — good or bad.

## Action Items
3 concrete things to focus on in the next trading week.

Keep it under 800 words. Use plain language. No generic advice — every point
must be grounded in their actual data. Use $ for monetary values."""


def _build_user_message(user_id: int, stats: dict, streak: dict, closed: list[dict]) -> str:
    lines = []
    lines.append("=== PERFORMANCE STATS ===")
    lines.append(f"Total trades: {stats['total']}  |  Win rate: {stats['win_rate']}%")
    lines.append(f"Wins: {stats['wins']}  |  Losses: {stats['losses']}")
    lines.append(f"Avg RR: {stats['avg_rr']}  |  Profit factor: {stats['profit_factor']}")
    lines.append(f"Total P&L: ${stats['total_pnl']}  |  Best: ${stats['best_trade']}  |  Worst: ${stats['worst_trade']}")
    lines.append(f"Avg win: ${stats['avg_win']}  |  Avg loss: ${stats['avg_loss']}")
    lines.append(f"Current streak: {streak['count']} {streak['type']}")
    lines.append("")

    lines.append("=== LAST 30 CLOSED TRADES ===")
    lines.append("Date       | Dir   | Entry    | Exit     | SL       | Result | PnL     | RR   | Score | Emotion    | Notes")
    lines.append("-" * 120)

    for t in closed[:30]:
        notes = (t.get("notes") or "")[:60].replace("\n", " ")
        lines.append(
            f"{t['date']}  | {t['direction']:5} | {t['entry_price']:8} | "
            f"{t.get('exit_price') or '—':8} | {t['sl_price']:8} | "
            f"{t['result']:6} | ${t.get('pnl', 0):7.2f} | "
            f"{t.get('rr_achieved', 0):4.2f} | {t.get('checklist_score', 0):5}/7 | "
            f"{(t.get('emotion') or '—'):10} | {notes}"
        )

    lines.append("")
    lines.append("Please analyze my trading journal and provide your mentor feedback.")
    return "\n".join(lines)


def _llm_analysis(user_id: int, stats: dict, streak: dict, closed: list[dict]) -> dict:
    try:
        import anthropic
        from goldart.config import ANTHROPIC_API_KEY, MENTOR_MODEL

        user_message = _build_user_message(user_id, stats, streak, closed)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=MENTOR_MODEL,
            max_tokens=1500,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return {"analysis": response.content[0].text, "mode": "ai"}

    except ImportError:
        return {"error": "anthropic package not installed. Run: pip install anthropic"}
    except Exception as e:
        log.exception("Mentor API call failed for user %s", user_id)
        return {"error": f"AI service error: {e}"}


# ══════════════════════════════════════════════════════════════════════════════
# RULE-BASED ANALYSIS (no API needed)
# ══════════════════════════════════════════════════════════════════════════════

def _rule_based_analysis(stats: dict, streak: dict, closed: list[dict]) -> dict:
    sections = []
    sections.append(_rb_performance_summary(stats, streak, len(closed)))
    sections.append(_rb_strengths(stats, closed))
    sections.append(_rb_areas_to_improve(stats, closed))
    sections.append(_rb_pattern_analysis(closed))
    sections.append(_rb_trade_callouts(closed))
    sections.append(_rb_action_items(stats, closed))

    # Convert sections to markdown text (same format as LLM output)
    parts = []
    for s in sections:
        parts.append(f"## {s['title']}")
        for line in s["lines"]:
            if s["title"] in ("Strengths", "Areas to Improve", "Pattern Analysis", "Action Items", "Trade Callouts"):
                parts.append(f"- {line}")
            else:
                parts.append(line)
        parts.append("")

    return {"analysis": "\n".join(parts), "mode": "local"}


def _rb_performance_summary(stats: dict, streak: dict, total_closed: int) -> dict:
    wr = stats["win_rate"]
    pf = stats["profit_factor"]
    pnl = stats["total_pnl"]

    if wr >= 60 and pf >= 1.5:
        tone = "Strong performance overall."
    elif wr >= 50 and pf >= 1.0:
        tone = "Solid foundation with room for improvement."
    elif wr >= 40:
        tone = "Below-average win rate — focus on trade selection."
    else:
        tone = "Significant room for improvement — tighten your process."

    lines = [
        f"{tone} Across {total_closed} closed trades, your win rate is "
        f"**{wr}%** with a profit factor of **{pf}**.",
        f"Total P&L: **${pnl:+.2f}** | Avg win: **${stats['avg_win']:.2f}** | "
        f"Avg loss: **${stats['avg_loss']:.2f}** | Avg RR: **{stats['avg_rr']:.2f}**",
    ]
    if streak["count"] >= 3:
        label = "wins" if streak["type"] == "WIN" else "losses"
        lines.append(f"Currently on a **{streak['count']}-trade {label} streak** — "
                     f"{'keep it going!' if streak['type'] == 'WIN' else 'time to step back and review.'}")

    return {"title": "Performance Summary", "lines": lines}


def _rb_strengths(stats: dict, closed: list[dict]) -> dict:
    points = []
    if stats["win_rate"] >= 50:
        points.append(f"Win rate of **{stats['win_rate']}%** shows good trade selection discipline.")
    if stats["profit_factor"] >= 1.5:
        points.append(f"Profit factor of **{stats['profit_factor']}** — winners outsize losers significantly.")
    if stats["avg_rr"] >= 1.5:
        points.append(f"Average RR of **{stats['avg_rr']:.2f}** indicates strong reward targeting.")

    scored = [t for t in closed if t.get("checklist_score") is not None]
    if scored:
        avg_score = sum(t["checklist_score"] for t in scored) / len(scored)
        if avg_score >= 5:
            points.append(f"Average checklist score of **{avg_score:.1f}/7** shows strong pre-trade discipline.")

    if stats["best_trade"] > 0 and abs(stats["worst_trade"]) > 0:
        ratio = stats["best_trade"] / abs(stats["worst_trade"])
        if ratio >= 2:
            points.append(f"Best trade (${stats['best_trade']:.2f}) is **{ratio:.1f}x** your worst loss — good asymmetry.")

    if not points:
        points.append("Keep building your track record — patterns will emerge with more data.")
    return {"title": "Strengths", "lines": points[:4]}


def _rb_areas_to_improve(stats: dict, closed: list[dict]) -> dict:
    points = []
    if stats["win_rate"] < 50:
        points.append(f"Win rate at **{stats['win_rate']}%** — review entry criteria. Are you forcing trades?")
    if 0 < stats["profit_factor"] < 1.0:
        points.append(f"Profit factor below 1.0 (**{stats['profit_factor']}**) — losses outweigh wins.")
    if 0 < stats["avg_rr"] < 1.0:
        points.append(f"Average RR of **{stats['avg_rr']:.2f}** is below 1:1 — risking more than you're making.")
    if abs(stats["worst_trade"]) > stats["avg_win"] * 3 and stats["avg_win"] > 0:
        points.append(f"Worst trade (${stats['worst_trade']:.2f}) is **{abs(stats['worst_trade'] / stats['avg_win']):.1f}x** your avg win — one blowup erases many gains.")

    emotion_losses = [t for t in closed if t.get("emotion") and t["result"] == "LOSS"
                      and t["emotion"].upper() in ("FOMO", "REVENGE", "FEAR", "GREEDY", "ANXIOUS")]
    if len(emotion_losses) >= 2:
        emotions = set(t["emotion"].upper() for t in emotion_losses)
        points.append(f"**{len(emotion_losses)} losses** linked to emotional trading ({', '.join(emotions)}).")

    scored = [t for t in closed if t.get("checklist_score") is not None]
    if scored:
        low = [t for t in scored if t["checklist_score"] < 4]
        if len(low) / len(scored) > 0.3:
            points.append(f"**{len(low)}/{len(scored)}** trades with checklist below 4/7 — are you skipping the process?")

    if not points:
        points.append("No major red flags — maintain consistency and keep journaling.")
    return {"title": "Areas to Improve", "lines": points[:4]}


def _rb_pattern_analysis(closed: list[dict]) -> dict:
    lines = []

    # Emotion correlation
    emotion_map = defaultdict(lambda: {"wins": 0, "losses": 0})
    for t in closed:
        em = (t.get("emotion") or "").strip().upper()
        if em and t["result"] in ("WIN", "LOSS"):
            emotion_map[em]["wins" if t["result"] == "WIN" else "losses"] += 1

    if emotion_map:
        for em, counts in emotion_map.items():
            total = counts["wins"] + counts["losses"]
            if total >= 2:
                wr = counts["wins"] / total * 100
                if wr < 40:
                    lines.append(f"**{em}** trades: **{wr:.0f}%** win rate — this emotion is costing you money.")
                elif wr > 65:
                    lines.append(f"**{em}** trades: **{wr:.0f}%** win rate — your optimal mindset.")

    # Checklist correlation
    high = [t for t in closed if (t.get("checklist_score") or 0) >= 5 and t["result"] in ("WIN", "LOSS")]
    low = [t for t in closed if t.get("checklist_score") is not None and (t.get("checklist_score") or 0) < 5 and t["result"] in ("WIN", "LOSS")]
    if len(high) >= 3 and len(low) >= 3:
        high_wr = sum(1 for t in high if t["result"] == "WIN") / len(high) * 100
        low_wr = sum(1 for t in low if t["result"] == "WIN") / len(low) * 100
        if abs(high_wr - low_wr) >= 10:
            lines.append(
                f"High checklist (5+/7): **{high_wr:.0f}%** WR vs low (<5/7): **{low_wr:.0f}%** — "
                f"{'the process works.' if high_wr > low_wr else 'checklist needs recalibration.'}"
            )

    # Direction bias
    longs = [t for t in closed if t.get("direction") == "LONG" and t["result"] in ("WIN", "LOSS")]
    shorts = [t for t in closed if t.get("direction") == "SHORT" and t["result"] in ("WIN", "LOSS")]
    if len(longs) >= 3 and len(shorts) >= 3:
        long_wr = sum(1 for t in longs if t["result"] == "WIN") / len(longs) * 100
        short_wr = sum(1 for t in shorts if t["result"] == "WIN") / len(shorts) * 100
        long_pnl = sum(float(t.get("pnl") or 0) for t in longs)
        short_pnl = sum(float(t.get("pnl") or 0) for t in shorts)
        bias_note = ""
        if abs(long_wr - short_wr) > 15:
            bias_note = f" — notably better at {'longs' if long_wr > short_wr else 'shorts'}."
        lines.append(f"**LONG**: {long_wr:.0f}% WR (${long_pnl:+.2f}) | **SHORT**: {short_wr:.0f}% WR (${short_pnl:+.2f}){bias_note}")

    # 4H bias alignment
    aligned = [t for t in closed if t.get("bias_4h") and t.get("direction") and t["result"] in ("WIN", "LOSS")]
    if len(aligned) >= 3:
        with_bias = [t for t in aligned
                     if (t["bias_4h"].upper() == "BULLISH" and t["direction"] == "LONG")
                     or (t["bias_4h"].upper() == "BEARISH" and t["direction"] == "SHORT")]
        against = [t for t in aligned if t not in with_bias]
        if len(with_bias) >= 2 and len(against) >= 2:
            w_wr = sum(1 for t in with_bias if t["result"] == "WIN") / len(with_bias) * 100
            a_wr = sum(1 for t in against if t["result"] == "WIN") / len(against) * 100
            lines.append(
                f"With 4H bias: **{w_wr:.0f}%** WR ({len(with_bias)} trades) | "
                f"Against: **{a_wr:.0f}%** WR ({len(against)} trades)"
                + (" — the higher TF trend matters." if w_wr > a_wr + 10 else "")
            )

    if not lines:
        lines.append("Not enough varied data to detect patterns — keep logging emotions, bias, and checklist scores.")
    return {"title": "Pattern Analysis", "lines": lines}


def _rb_trade_callouts(closed: list[dict]) -> dict:
    lines = []
    rated = [t for t in closed if t.get("pnl") is not None]
    if not rated:
        return {"title": "Trade Callouts", "lines": ["No closed trades with P&L data to highlight."]}

    best = max(rated, key=lambda t: float(t.get("pnl") or 0))
    if float(best.get("pnl") or 0) > 0:
        lines.append(
            f"**Best**: {best['date']} {best.get('direction','')} — "
            f"**${float(best['pnl']):+.2f}** (RR {float(best.get('rr_achieved') or 0):.2f})"
            + (f" | Score {best['checklist_score']}/7" if best.get("checklist_score") else "")
            + (f" | {best['emotion']}" if best.get("emotion") else "")
        )

    worst = min(rated, key=lambda t: float(t.get("pnl") or 0))
    if float(worst.get("pnl") or 0) < 0:
        lines.append(
            f"**Worst**: {worst['date']} {worst.get('direction','')} — "
            f"**${float(worst['pnl']):+.2f}** (RR {float(worst.get('rr_achieved') or 0):.2f})"
            + (f" | Score {worst['checklist_score']}/7" if worst.get("checklist_score") else "")
            + (f" | {worst['emotion']}" if worst.get("emotion") else "")
        )

    recent_losses = [t for t in closed[:10] if t["result"] == "LOSS" and t is not worst]
    if recent_losses:
        rl = recent_losses[0]
        note = (rl.get("notes") or "")[:80]
        lines.append(
            f"**Recent loss**: {rl['date']} {rl.get('direction','')} — ${float(rl.get('pnl') or 0):+.2f}"
            + (f" — \"{note}\"" if note else "")
        )

    if not lines:
        lines.append("Keep logging trades — callouts appear as your journal grows.")
    return {"title": "Trade Callouts", "lines": lines}


def _rb_action_items(stats: dict, closed: list[dict]) -> dict:
    items = []
    if stats["win_rate"] < 50:
        items.append("Only take trades with checklist score 5+ this week — filter aggressively.")
    if stats["avg_rr"] < 1.5:
        items.append("Target minimum 1.5:1 RR on every trade — adjust TP before entry.")

    no_emotion = [t for t in closed if not t.get("emotion")]
    if len(no_emotion) > len(closed) * 0.3:
        items.append(f"Log emotions on every trade — {len(no_emotion)}/{len(closed)} missing.")

    no_notes = [t for t in closed if not t.get("notes")]
    if len(no_notes) > len(closed) * 0.5:
        items.append(f"Add notes to trades — {len(no_notes)}/{len(closed)} have none.")

    if 0 < stats["profit_factor"] < 1.0:
        items.append("Cut position size by 50% until profit factor exceeds 1.0.")

    emotion_losses = [t for t in closed if t.get("emotion") and t["result"] == "LOSS"
                      and t["emotion"].upper() in ("FOMO", "REVENGE")]
    if emotion_losses:
        items.append("Feeling FOMO or revenge? Walk away 15 minutes before placing any trade.")

    if stats["win_rate"] >= 55 and stats["profit_factor"] >= 1.3:
        items.append("Your edge is working — focus on consistency. Don't fix what isn't broken.")

    if not items:
        items = [
            "Review your last 5 losses for common patterns.",
            "No trade below checklist score 5/7 this week.",
            "Journal every trade with emotion + notes within 5 minutes of exit.",
        ]
    return {"title": "Action Items", "lines": items[:4]}
