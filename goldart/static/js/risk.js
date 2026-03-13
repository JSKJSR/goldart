// risk.js — isolated risk calculator module
"use strict";

async function calcRisk() {
  const entry = parseFloat(document.getElementById("rcEntry")?.value);
  const sl    = parseFloat(document.getElementById("rcSL")?.value);
  const dir   = document.getElementById("rcDir")?.value || "LONG";

  if (!entry || !sl) {
    alert("Enter both Entry and Stop Loss prices.");
    return;
  }

  try {
    const { ok, data, error } = await api("/analysis/api/risk", {
      method: "POST",
      body: JSON.stringify({ entry, sl, direction: dir }),
    });

    if (!ok) { alert(error); return; }

    setEl("outLot",    data.lot_size);
    setEl("outTP",     data.tp);
    setEl("outRisk",   `$${data.risk_usd}`);
    setEl("outReward", `$${data.reward_usd}`);
    setEl("outRR",     `1:${data.rr_ratio}`);

    // Pre-fill the Log Trade link with query params
    const logBtn = document.getElementById("logTradeBtn");
    if (logBtn) {
      const params = new URLSearchParams({
        entry, sl, tp: data.tp, lot: data.lot_size, dir
      });
      logBtn.href = `/trades/new?${params}`;
    }

  } catch (e) {
    alert("Risk calculation failed: " + e.message);
  }
}
