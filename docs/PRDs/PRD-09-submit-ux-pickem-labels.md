# PRD-09: Submit UX + Pick'em Labels

## 1. Problem Statement and Context

### What
Frontend-only polish for the Picks save path and spread display. Sync throws inside `Promise.allSettled` must not abort sibling requests. Save must never use `alert()`. Submit errors must not hide the picks/tiebreaker grid. Zero spreads must render as Pick'em, never ±0.

### Background
PRD-06 added parallel submit, a pre-submit incomplete modal, and partial-success merging. Remaining bugs: `throw` inside `allSettled().map()` rejects the whole submit; `alert()` is the save toast; a shared `error` flag hides the grid (`error ? null`); lock-without-a-team is allowed; zero lines still render as `-0` / `+0` on Live, Leaderboard, Admin Games, and User Picks.

### Related Work
- [PRD-06](https://github.com/eweinhaus/March-Madness-Spreads-League/pull/29) concurrency + submit UX
- Server lock/week bounds stay authoritative — do not reintroduce client lock rules that contradict them

### Out of scope
- Backend scoring or APIs
- Firestore wipes or data migrations
- Changing the pre-submit incomplete Modal
- Sequential submit (keep parallel `allSettled`)

---

## 2. Must-haves

1. **`runSubmitPicks` never sync-throws inside `allSettled` `.map()`.** Wrap each item in `Promise.resolve().then` / `async` so a missing team is a rejected promise. Attach a display `label` on errors.
2. **`handleLockToggle`:** turning lock ON without `picks[gid] || existingPicks[gid]` sets an inline error `Select a team before setting your {lockLabel}.` and does not update locks. Unlock remains allowed.
3. **Remove `alert()` from Save.** Use a dismissible Bootstrap `Alert` via `submitFeedback { variant, message, failedLabels }`. Name failed matchups/TBs (up to ~5, then `and N more`). Merge successes; leave failed items dirty.
4. **Split `loadError` vs `submitFeedback`:** `loadError` may hide the grid; submit errors must not (`error ? null` is the bug).
5. **Add `src/utils/spreadDisplay.js`:**
   - `isPickEm(spread)`: `Number` + `Math.abs(n) < 1e-9`
   - `formatSpreadFavorite(spread, homeTeam, awayTeam)`
   - `formatSpreadSideSuffix(spread, side)`
   Wire into Picks, Live, Leaderboard, AdminGames, UserPicksModal. No ±0 anywhere. Non-zero spreads unchanged.
6. **Keep parallel `allSettled`.** Pre-submit incomplete Modal stays.

---

## 3. Success criteria

- Missing-team and HTTP failures reject per-item; siblings still settle.
- Failed labels show matchup or TB question, capped at five plus remainder count.
- Lock icon without a team shows the inline message and leaves `locks` unchanged.
- Save success/partial/failure uses dismissible `Alert`; grid stays visible.
- Load failure still hides the grid.
- Spread `0` / `-0` / tiny float → `Pick'em` or empty side suffix; `3` / `-7` strings unchanged.
