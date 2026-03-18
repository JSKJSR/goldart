const GOLD_PIP = 100.0;

function calcTradePnl(entry, exit, sl, lot, direction) {
  const mult = direction === 'LONG' ? 1 : -1;
  const slDist = Math.abs(entry - sl);
  const pnl = (exit - entry) * mult * lot * GOLD_PIP;
  const rr = slDist > 0 ? Math.abs(exit - entry) / slDist : 0;
  return { pnl, rr };
}

function autoSelectResult(pnl) {
  if (Math.abs(pnl) < 0.50) return 'BE';
  return pnl > 0 ? 'WIN' : 'LOSS';
}
