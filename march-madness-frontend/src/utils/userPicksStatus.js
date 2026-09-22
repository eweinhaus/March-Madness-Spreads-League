/**
 * Combined admin User Picks status: "N/M · lock set|no lock"
 * instead of separate Submitted / Missing Picks badges.
 */
export function formatUserPicksStatus(user = {}, { expectsLock = true } = {}) {
  const picksMade = Number(user.picks_made) || 0;
  const totalGames = Number(user.total_games) || 0;
  const hasLock = Boolean(user.has_current_period_lock);
  const lockFragment = hasLock ? "lock set" : "no lock";

  if (totalGames === 0) {
    return {
      text: hasLock ? `No games remaining · ${lockFragment}` : "No games remaining",
      variant: "secondary",
    };
  }

  const text = `${picksMade}/${totalGames} · ${lockFragment}`;

  if (user.is_complete && hasLock) {
    return { text, variant: "success" };
  }
  if (user.is_complete && !hasLock) {
    return { text, variant: expectsLock ? "warning" : "success" };
  }
  if (!user.is_complete && hasLock) {
    return { text, variant: "warning" };
  }
  return { text, variant: "danger" };
}
