/**
 * Lock-only incomplete: lock UI is on, at least one open game has no pick,
 * and the user already has an effective lock on the open slate.
 */
export function isLockOnlyIncomplete({
  showLockUI,
  warnings,
  availableGames,
  locks = {},
  existingLocks = {},
} = {}) {
  if (!showLockUI) return false;
  if (!warnings?.missingGames?.length) return false;
  if (!availableGames?.length) return false;

  return availableGames.some((game) => {
    const gid = String(game.game_id);
    if (locks[gid] !== undefined) return Boolean(locks[gid]);
    return Boolean(existingLocks[gid]);
  });
}

export function lockOnlyWarningCopy({
  lockLabel,
  pickedCount,
  openCount,
  missingCount,
} = {}) {
  const label = lockLabel || "lock";
  const picked = Number(pickedCount) || 0;
  const open = Number(openCount) || 0;
  const missing = Number(missingCount) || 0;
  return `You're saving your ${label} but only ${picked} of ${open} open games have a pick. ${missing} game(s) will stay blank.`;
}
