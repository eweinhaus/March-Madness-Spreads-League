/** True when the spread is numerically zero (including -0 and tiny floats). */
export function isPickEm(spread) {
  const n = Number(spread);
  return Number.isFinite(n) && Math.abs(n) < 1e-9;
}

/**
 * Favorite-style line for a game card/badge.
 * Convention: positive spread = home favorite.
 * Pick'em returns "Pick'em" — never ±0.
 */
export function formatSpreadFavorite(spread, homeTeam, awayTeam) {
  if (isPickEm(spread)) return "Pick'em";
  const n = Number(spread);
  if (!Number.isFinite(n)) return "";
  return n > 0 ? `${homeTeam} -${n}` : `${awayTeam} -${Math.abs(n)}`;
}

/**
 * Signed line suffix for one side of the matchup (leading space when present).
 * Pick'em returns "" so callers never render ±0.
 * @param {unknown} spread
 * @param {"home"|"away"} side
 */
export function formatSpreadSideSuffix(spread, side) {
  if (isPickEm(spread)) return "";
  const n = Number(spread);
  if (!Number.isFinite(n)) return "";
  const isHome = side === "home";
  if (n > 0) return isHome ? ` -${n}` : ` +${n}`;
  return isHome ? ` +${Math.abs(n)}` : ` -${Math.abs(n)}`;
}

/**
 * Away @ Home plus the home team's line, or "Pick'em" instead of ±0.
 * Non-zero spreads keep the existing " +X" / " -X" home-line format.
 */
export function formatMatchupWithHomeLine(spread, homeTeam, awayTeam) {
  if (isPickEm(spread)) return `${awayTeam} @ ${homeTeam} Pick'em`;
  const n = Number(spread);
  if (!Number.isFinite(n)) return `${awayTeam} @ ${homeTeam}`;
  return n < 0
    ? `${awayTeam} @ ${homeTeam} +${Math.abs(n)}`
    : `${awayTeam} @ ${homeTeam} -${n}`;
}
