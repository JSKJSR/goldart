// app.js — shared utilities loaded on every page
"use strict";

// ── Fetch helper ──────────────────────────────────────────────────────────────
async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Load snapshot → populate all 3 columns ───────────────────────────────────
let _countdownTimer = null;

async function loadSnapshot() {
  const btn = document.getElementById("refreshBtn");
  if (btn) { btn.textContent = "↻ Loading…"; btn.disabled = true; }

  try {
    const resp = await api("/analysis/api/snapshot");

    if (!resp.ok) {
      setEl("signalContent", `<span class="red">⚠ ${resp.error}</span>`);
      _startCountdown(60, btn);   // still cool down on error
      return;
    }

    const { data, cached, age, refresh_in } = resp;

    _populateSignal(data);
    _populateTrend(data);
    _populateEma(data);
    _populateLevels(data);
    _populateFib(data);
    _autoTickChecklist(data);

    // Show cache status badge next to refresh button
    _setCacheStatus(cached, age);

    // Start countdown — button re-enables when cache expires
    _startCountdown(refresh_in, btn);

  } catch (e) {
    setEl("signalContent", `<span class="red">Server unreachable: ${e.message}</span>`);
    if (btn) { btn.textContent = "↻ Refresh"; btn.disabled = false; }
  }
}

// ── Cache status + countdown ──────────────────────────────────────────────────
function _setCacheStatus(cached, age) {
  const el = document.getElementById("cacheStatus");
  if (!el) return;
  if (cached) {
    el.textContent  = `data ${age}s old`;
    el.style.color  = age > 45 ? "var(--gold)" : "var(--muted)";
  } else {
    el.textContent  = "live ✓";
    el.style.color  = "var(--green)";
  }
}

function _startCountdown(seconds, btn) {
  if (_countdownTimer) clearInterval(_countdownTimer);
  if (!btn) return;

  let remaining = Math.max(seconds, 0);

  const tick = () => {
    if (remaining <= 0) {
      clearInterval(_countdownTimer);
      btn.textContent = "↻ Refresh";
      btn.disabled    = false;
      return;
    }
    btn.textContent = `↻ ${remaining}s`;
    remaining--;
  };

  tick();
  _countdownTimer = setInterval(tick, 1000);
}

// ── Signal box ────────────────────────────────────────────────────────────────
function _populateSignal(d) {
  const stars = "★".repeat(d.score) + "☆".repeat(5 - d.score);
  const cls   = d.signal_active ? "signal-active" : "signal-inactive";
  const label = d.signal_active
    ? `<span style="color:var(--gold);font-weight:700">⚡ SETUP DETECTED</span>`
    : `<span style="color:var(--muted)">No setup — keep watching</span>`;

  const tags = [
    d.at_ema21 || d.at_ema15 ? `<span class="sig-tag sig-tag--on">EMA ✓</span>`   : `<span class="sig-tag">EMA —</span>`,
    d.at_fib618              ? `<span class="sig-tag sig-tag--on">Fib ✓</span>`   : `<span class="sig-tag">Fib —</span>`,
    d.at_sr                  ? `<span class="sig-tag sig-tag--on">S/R ✓</span>`   : `<span class="sig-tag">S/R —</span>`,
    d.valid_signal           ? `<span class="sig-tag sig-tag--on">Candle ✓</span>`: `<span class="sig-tag">Candle —</span>`,
  ].join("");

  setEl("signalContent", `
    <div class="${cls}">
      <div class="signal-stars">${stars}</div>
      ${label}
      <div class="signal-tags">${tags}</div>
    </div>
  `);
}

// ── Trend ─────────────────────────────────────────────────────────────────────
function _populateTrend(d) {
  setBadge("trend4h", d.trend_4h);
  setBadge("trend1h", d.trend_1h);

  const alignedEl = document.getElementById("trendAligned");
  if (alignedEl) {
    alignedEl.textContent = d.aligned ? "✅ Aligned — trade with trend" : "⚠️ Not aligned — wait";
    alignedEl.style.color = d.aligned ? "var(--green)" : "var(--gold)";
  }
}

// ── EMA (15M) ─────────────────────────────────────────────────────────────────
function _populateEma(d) {
  setEl("currentPrice", d.current_price);
  setEl("ema15", d.ema.ema15);
  setEl("ema21", d.ema.ema21);

  const statusEl = document.getElementById("emaStatus");
  if (statusEl) {
    if (d.at_ema21)      statusEl.textContent = "⚡ Price at EMA 21 — watch for candle";
    else if (d.at_ema15) statusEl.textContent = "⚡ Price at EMA 15 — watch for candle";
    else                 statusEl.textContent = "";
  }
}

// ── Key Levels (major 4H + minor 1H) ─────────────────────────────────────────
function _populateLevels(d) {
  const price = d.current_price;

  // Major (4H)
  let majorHtml = "";
  (d.sr_major.resistance || []).forEach(r => {
    majorHtml += `<div class="level-row"><span class="lvl-label lvl-res">R</span><span>${r}</span></div>`;
  });
  majorHtml += `<div class="level-row price-row">
    <span class="lvl-label">▶</span><span>${price}</span>
  </div>`;
  (d.sr_major.support || []).forEach(s => {
    majorHtml += `<div class="level-row"><span class="lvl-label lvl-sup">S</span><span>${s}</span></div>`;
  });
  setEl("majorLevels", majorHtml);

  // Minor (1H)
  let minorHtml = "";
  (d.sr_minor.resistance || []).forEach(r => {
    minorHtml += `<div class="level-row level-row--minor"><span class="lvl-label lvl-res">R</span><span>${r}</span></div>`;
  });
  (d.sr_minor.support || []).forEach(s => {
    minorHtml += `<div class="level-row level-row--minor"><span class="lvl-label lvl-sup">S</span><span>${s}</span></div>`;
  });
  setEl("minorLevels", minorHtml || "<span style='color:var(--muted);font-size:10px'>—</span>");
}

// ── Fibonacci ─────────────────────────────────────────────────────────────────
function _populateFib(d) {
  setEl("fibSwing", `Swing H: ${d.swing_high} · L: ${d.swing_low}`);

  let html = "";
  Object.entries(d.fibs).forEach(([label, val]) => {
    const isKey = label === "0.618";
    html += `
      <div class="level-row ${isKey ? "fib-key-row" : ""}">
        <span>${label}${isKey ? " ★" : ""}</span>
        <span>${val}</span>
      </div>`;
  });
  setEl("fibContent", html);
}

// ── Auto-tick checklist from API data ────────────────────────────────────────
// Saves the trader from ticking obvious items already confirmed by the engine
function _autoTickChecklist(d) {
  // c1: 4H trend clear
  _autotick("c1", d.trend_4h !== "RANGING");
  _autotick("hint-c1", null, d.trend_4h);

  // c2: 1H aligned with 4H
  _autotick("c2", d.aligned);
  _autotick("hint-c2", null, d.aligned ? "✓ aligned" : "not aligned");

  // c3: price at S/R
  _autotick("c3", d.at_sr);
  _autotick("hint-c3", null, d.nearest_major ? `near ${d.nearest_major}` : "—");

  // c4: fib 0.618
  _autotick("c4", d.at_fib618);
  _autotick("hint-c4", null, `0.618 @ ${d.fib_618}`);

  // c5: at EMA
  _autotick("c5", d.at_ema21 || d.at_ema15);
  _autotick("hint-c5", null, d.at_ema21 ? "@ EMA21" : d.at_ema15 ? "@ EMA15" : "—");

  // c6: signal candle — trader must confirm manually (they see the chart)
  _autotick("hint-c6", null, d.valid_signal ? "engine: yes" : "check chart");

  // c7: daily losses — pre-filled from session (hint set in template)

  updateScore();
}

function _autotick(name, checked, hintText) {
  if (hintText !== null && hintText !== undefined) {
    const el = document.getElementById(name);
    if (el) { el.textContent = hintText; return; }
  }
  const box = document.querySelector(`input[name="${name}"]`);
  if (box && checked !== null) box.checked = checked;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setEl(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function setBadge(id, trend) {
  const el = document.getElementById(id);
  if (!el) return;
  const map = { BULLISH: "trend-bullish", BEARISH: "trend-bearish", RANGING: "trend-ranging" };
  el.className = `trend-badge ${map[trend] || "trend-ranging"}`;
  el.textContent = trend || "—";
}
