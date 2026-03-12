// checklist.js — isolated checklist module
"use strict";

const TOTAL = 7;
const UNLOCK_AT = 6;

function updateScore() {
  const boxes   = document.querySelectorAll(".check-list input[type=checkbox]");
  const checked = [...boxes].filter(b => b.checked).length;
  const pct     = Math.round((checked / TOTAL) * 100);

  // Score display
  setEl("scoreNum", checked);

  // Bar
  const fill = document.getElementById("scoreFill");
  if (fill) {
    fill.style.width = pct + "%";
    fill.style.background = checked >= UNLOCK_AT ? "var(--green)" : "var(--gold)";
  }

  // Verdict
  const verdict = document.getElementById("scoreVerdict");
  if (verdict) {
    if (checked === TOTAL)         { verdict.textContent = "✅ PERFECT — Trade cleared"; verdict.style.color = "var(--green)"; }
    else if (checked >= UNLOCK_AT) { verdict.textContent = "✅ CLEARED — Good setup";    verdict.style.color = "var(--green)"; }
    else if (checked >= 4)         { verdict.textContent = "⚠️ WEAK — Review setup";      verdict.style.color = "var(--gold)"; }
    else                           { verdict.textContent = "❌ NOT READY";                verdict.style.color = "var(--red)";  }
  }

  // Unlock risk calculator
  const calc = document.getElementById("riskCalc");
  if (calc) {
    calc.classList.toggle("unlocked", checked >= UNLOCK_AT);
  }

  // Store score for trade form
  const hidden = document.getElementById("hiddenScore");
  if (hidden) hidden.value = checked;
}
