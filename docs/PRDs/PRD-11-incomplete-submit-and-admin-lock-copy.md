# PRD-11: Incomplete Submit Guard + Admin Lock Copy

## 1. Problem Statement and Context

### What
Stop players from accidentally saving a lock-only (or otherwise incomplete) week without understanding what they are skipping, and stop the admin User Picks page from looking like the app ate their picks when lock Submitted sits next to Missing Picks / `0/N`.

Three changes, all frontend-first (one small optional admin API field only if needed for copy):

1. **Load-gate Save** — `Save Picks` stays disabled until the Picks page has finished loading sport config + games/tiebreakers.
2. **Clearer lock-only confirm** — when the incomplete modal would fire and the user has a lock set for the current open slate but is missing picks, lead with an explicit "you're only locking X of Y" warning; demote **Save anyway** so **Go back** is the primary action; require a second tap on Save anyway for that lock-only case on all viewports.
3. **Admin badge copy** — User Picks rows show progress + lock as one readable status (e.g. `0/12 · lock set`) instead of green **Submitted** next to yellow **Missing Picks**, which players and admins read as data loss.

### Background
Blair Summers (2026-09 week) saved a lock of the week on Colorado @ Georgia Tech and left the other 11 open games blank. The existing **Before you submit** modal in `Picks.jsx` already lists missing games and offers **Save anyway**. He almost certainly dismissed it (or saved on a half-ready state). Admin then showed lock **Submitted** + **Missing Picks** / low `picks_made`, which looked like a bug. Data was correct; UX was not.

Pierce Jarrett's lock was fine in the DB (Tulane @ Duke); that was timing / expectation, not this PRD's primary fix.

Related live behavior (do not reopen):
- PR #36 — LOTW lock-on txn generator fix
- PR #37 — admin `has_current_period_lock` uses upcoming-slate week; lock-preferring pick collapse

### Related Work
- `march-madness-frontend/src/pages/Picks.jsx` — `computeSubmitWarnings`, `onSubmitClick`, incomplete `Modal`, `isLoading` / `configLoading`
- `march-madness-frontend/src/pages/AdminUserPicks.jsx` — Missing Picks / Submitted badges, Locks Completed bar
- PRD-09 — submit Alert / no `window.alert` / lock-needs-team (keep those)
- PRD-10 — hidden users (admin lists already omit Ethan/Herbie)

### Out of scope
- Changing lock period math or `has_current_period_lock` (done in #37)
- Blocking partial saves entirely (product still allows intentional incomplete saves)
- Typing `CONFIRM` to proceed (too heavy for a pick pool)
- Email / push reminders for incomplete weeks
- Entering picks for Blair or any player
- Season wipe

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Why |
|------|-----|
| `march-madness-frontend/src/pages/Picks.jsx` | Load-gate Save; rewrite incomplete modal for lock-only; second-tap Save anyway |
| `march-madness-frontend/src/pages/AdminUserPicks.jsx` | Replace dual badges with combined progress · lock copy |
| `march-madness-frontend/src/hooks` / sport config provider | `configLoading` already used on Picks |
| Backend `/admin/user_picks_status` | Already returns `picks_made`, `total_games`, `has_current_period_lock`, `is_complete` — enough for copy; no API change required |

### Similar Implementations
- Incomplete modal already built (PRD-06/09 era): `computeSubmitWarnings` → `setShowSubmitWarning(true)` → **Go back** / **Save anyway**.
- Save row already disables on `isSubmitting || isCheckingWarnings`.
- Full-page spinner already shows when `configLoading || isLoading` — but Save can still appear in edge timings; make the button itself gated.

### Architecture Notes
- Frontend-only for all three must-haves.
- Do **not** hardcode player names (Blair/Pierce) in code.
- Keep parallel `allSettled` submit and dismissible submit `Alert` from PRD-09.
- Modal must remain Bootstrap `Modal`, not `window.alert`.

### Database/API Context
No Firestore schema changes. Admin endpoint fields stay:

```json
{
  "picks_made": 0,
  "total_games": 12,
  "is_complete": false,
  "has_current_period_lock": true
}
```

---

## 3. Design Decisions (Pre-Made)

### Approach

**A. Load-gate Save**
- `Save Picks` `disabled` when any of: `isSubmitting`, `isCheckingWarnings`, `isLoading`, `configLoading`.
- While disabled for loading, show a short helper under the button or as `title` tooltip: `Loading games…` (only when loading, not when merely no unsaved changes).
- Do not render the Save row until `!(configLoading || isLoading)` **and** there are unsaved changes (same unsaved keys as today: `picks` / `locks` / `tiebreakerPicks`).
- If a background refresh sets loading true again, disable Save immediately.

**B. Clearer lock-only confirm (extend existing modal)**
Define lock-only incomplete as:

```text
showLockUI
AND missingGames.length > 0
AND user has at least one lock among availableGames
  (locks[gid] === true OR (locks[gid] === undefined && existingLocks[gid]))
```

When that is true, the modal must:
1. Change title to **`Save incomplete slate?`** (keep **Before you submit** for other incomplete cases: missing lock only, missing TBs only, missing games without any lock).
2. Lead with a warning alert (Bootstrap `Alert` `variant="warning"`), not muted small text:

```text
You're saving your {lockLabel} but only {pickedCount} of {openCount} open games have a pick.
{missingGames.length} game(s) will stay blank.
```

Where `openCount = availableGames.length` and `pickedCount = openCount - missingGames.length`.
3. Still list **Games without a pick** (existing list).
4. Footer: **Go back** = `variant="success"` (primary). **Save anyway** = `variant="outline-secondary"` (demoted).
5. **Second tap for Save anyway** when lock-only incomplete: first click changes the button label to **`Tap again to save incomplete`** (or **Click again to save incomplete** on `sm+`) and does not submit; second click within 4 seconds calls `confirmSubmitDespiteWarnings`. If 4 seconds pass, reset label. Cancel / Go back / modal close resets.
6. Non–lock-only incomplete (e.g. missing lock days only, or missing games with no lock set): keep current title/body pattern but still demote **Save anyway** to `outline-secondary` and keep **Go back** as primary `success`. No second-tap required unless lock-only.

**C. Admin User Picks copy**
Replace the two separate status badges (Missing Picks / All Picks Submitted and Submitted / Unsubmitted) with **one** status line per row:

| Condition | Display |
|-----------|---------|
| `total_games === 0` | `No games remaining` (+ lock fragment if `has_current_period_lock`: ` · lock set`) |
| `is_complete && has_current_period_lock` | `{picks_made}/{total_games} · lock set` (success styling) |
| `is_complete && !has_current_period_lock` | `{picks_made}/{total_games} · no lock` (success / warning for missing lock — use warning if football week expects a lock) |
| `!is_complete && has_current_period_lock` | `{picks_made}/{total_games} · lock set` (warning styling) |
| `!is_complete && !has_current_period_lock` | `{picks_made}/{total_games} · no lock` (warning/danger styling) |

Use `lockLabel` from sport config when easy (`lock set` is fine if config not on this page). Keep the progress bar. Keep **Locks Completed** summary bar; optionally rename label to **Locks set** for consistency (optional, not required).

Do **not** use the word **Submitted** alone for the lock badge anymore.

### Rationale
- Blair's miss was confirmation UX + possible load race, not bad lock math.
- Demoting Save anyway + second tap raises the cost of skipping without banning partial saves.
- Admin combined copy matches what Execute/QA told Ethan: badges were misread as data loss.

### Patterns/Libraries
- Existing React Bootstrap `Modal`, `Button`, `Alert`, `Badge`
- Existing `lockLabel` / `periodType` from `useSportConfig` / app config on Picks

### Code Organization
- Keep warning computation in `computeSubmitWarnings`; add a small helper `isLockOnlyIncomplete(warnings, availableGames, locks, existingLocks)` in `Picks.jsx` (or a tiny util next to it if the file is already huge).
- Admin copy helper: `formatUserPicksStatus(user)` in `AdminUserPicks.jsx`.

---

## 4. Implementation Guidance

### Step-by-step Plan
1. Gate Save on `isLoading` / `configLoading` as above.
2. Implement `isLockOnlyIncomplete` and branch modal title/body/footer.
3. Add second-tap state for Save anyway (`saveAnywayArmed` + timeout).
4. Rewrite AdminUserPicks status badges to combined copy.
5. Manual / light component checks; no backend deploy required for the happy path.

### Key Functions/Methods
- `computeSubmitWarnings` — unchanged math; still lists all missing open games
- `isLockOnlyIncomplete(...)` — new
- `confirmSubmitDespiteWarnings` — only called after second tap when lock-only
- `formatUserPicksStatus(user)` — new for admin row

### Data Flow
1. User opens Picks → spinner until load done → Save only after unsaved edits and load complete.
2. User sets lock, skips other games, hits Save → lock-only modal with counts → Go back (default) or double-tap Save anyway → existing `runSubmitPicks`.
3. Admin opens User Picks → sees `0/12 · lock set` for a Blair-shaped row.

### Complex Logic Breakdown
**Who counts as "has a lock" for lock-only?** Any `availableGames` entry with effective lock true. Do not require the lock to be in the unsaved `locks` map only — include `existingLocks` so a previously saved lock + new blank slate still warns if they hit Save with other dirty fields. If the only dirty field is something else and missing games remain, still show incomplete modal; lock-only branch applies whenever missing games + any effective lock on the open slate.

**Second tap:** store `saveAnywayArmedUntil = Date.now() + 4000` on first click; on second click if `Date.now() < saveAnywayArmedUntil`, submit; else re-arm.

### Code Examples

Save disabled (concept):

```jsx
const picksLoading = configLoading || isLoading;
// ...
<Button
  disabled={isSubmitting || isCheckingWarnings || picksLoading}
  onClick={onSubmitClick}
>
  Save Picks
</Button>
```

Lock-only footer (concept):

```jsx
<Button variant="success" onClick={() => setShowSubmitWarning(false)}>Go back</Button>
<Button variant="outline-secondary" onClick={onSaveAnywayClick}>
  {saveAnywayArmed ? "Tap again to save incomplete" : "Save anyway"}
</Button>
```

---

## 5. Edge Cases and Error Handling

### Edge Cases
- `availableGames.length === 0` — existing path: skip modal, submit (unchanged).
- Missing lock days only (all games picked, no lock) — not lock-only; use standard incomplete modal, demoted Save anyway, no second tap.
- Missing TBs only — same as above.
- Hidden admins (PRD-10) — unaffected; they still use Picks.
- Mobile: second-tap label uses "Tap again…"; desktop may use "Click again…" via Bootstrap `useBreakpoint` or simple CSS/`window.matchMedia` — either is fine; pick one and stay consistent.
- User arms Save anyway then hits Go back — reset armed state.

### Error Scenarios
- Load failure (`loadError`) — existing behavior: no grid / no Save. Do not offer Save anyway on a failed load.

### Validation Requirements
- Do not change server-side pick validation.
- Second tap must not submit on the first click under any race (disable button briefly or check armed flag synchronously).

### Error Messages
- Lock-only warning copy must include `{lockLabel}` so football says "lock of the week".

---

## 6. Likely Pitfalls to Avoid

### Common Mistakes
- Removing Save anyway entirely (product still wants intentional partial saves).
- Leaving Save anyway as solid green primary.
- Keeping admin badge text **Submitted** / **Unsubmitted** for locks.
- Hardcoding "12" or Blair's game count — always use `missingGames.length` / `availableGames.length` / API fields.

### Gotchas
- `computeSubmitWarnings` only sees **available** (unfrozen) games — correct; tipped games are out of scope for the modal.
- Save row currently mounts only when unsaved keys exist; keep that, and add load gate.
- Do not break lock-without-team inline error from PRD-09.

### Performance Concerns
- Negligible; no new network calls.

### Security Considerations
- None beyond existing auth on admin page.

### Integration Issues
- Sport config `lock_label` / `period_type` must keep driving copy.

---

## 7. Testing Requirements

### Test Scenarios
1. While `isLoading`, Save is not clickable even if local state were dirty.
2. Lock set + 11 missing games → modal title `Save incomplete slate?`, warning with `1 of 12` (or actual counts), Go back primary, Save anyway outline.
3. First Save anyway click does not call `runSubmitPicks`; second does.
4. Missing games, no lock → standard incomplete title; Save anyway demoted; no second tap required.
5. Admin row with `picks_made=0`, `total_games=12`, `has_current_period_lock=true` shows `0/12 · lock set` (warning), not "Submitted" + "Missing Picks".
6. Complete user with lock shows `12/12 · lock set` success.

### Unit Tests
- Prefer pure helpers: `isLockOnlyIncomplete`, `formatUserPicksStatus` with table-driven tests if the frontend already has a test runner; otherwise manual QA checklist is acceptable for this UI PRD.

### Manual Testing
- Desktop + phone-width: lock-only double confirm.
- Admin User Picks as signed-in admin: Blair-shaped row readable without looking like data loss.

### Test Data
- Local/dev user: set lock on one open game, leave others blank.

---

## 8. Acceptance Criteria

### Functional Requirements
- [ ] Save Picks disabled while `configLoading || isLoading`.
- [ ] Lock-only incomplete opens the stronger modal with picked/open counts and `{lockLabel}`.
- [ ] Go back is the primary button; Save anyway is demoted.
- [ ] Lock-only Save anyway requires two clicks/taps within 4 seconds.
- [ ] Non–lock-only incomplete still warns; Save anyway demoted; no second tap required.
- [ ] Admin User Picks no longer shows standalone lock **Submitted** / **Unsubmitted** badges; shows combined `N/M · lock set|no lock` (or equivalent).
- [ ] Partial save behavior and `allSettled` submit unchanged once confirmed.
- [ ] No season wipe; no hardcoded player names.

### User-Facing Behavior
- A Blair-shaped save is hard to do by accident.
- Admins reading User Picks see incomplete-with-lock as incomplete picks plus lock set, not "Submitted."

### Performance Requirements
- No new API round trips for the modal.

### Security Requirements
- Admin page remains admin-gated.

---

## 9. Dependencies and Considerations

### External Services
- None new.

### Database Changes
- None.

### Configuration
- Uses existing sport config labels.

### Breaking Changes
- Admin badge strings change (intentional).
- Save anyway interaction changes for lock-only (intentional).

### Migration Steps
1. Merge frontend deploy (Vercel web).
2. QA on Picks + Admin User Picks.
3. No Firestore CLI step.

---

## 10. Project Notes from Ticket

### Important Notes
- Came from Spread Pools Chat after Blair/Pierce support thread (Sep 3, 2026). Room consensus: load-gate + clearer lock-only confirm; admin `0/12 · lock set` follow-on included in this same PRD so we do not ship half the fix.
- Do not treat Pierce's earlier Unsubmitted report as a separate bug in this PRD.
- Execute → PR Reviewer → QA pipeline after this file lands (same as PRD-10).

### Assumptions
- Blair hit Save anyway or an equivalent easy dismiss; strengthening confirm is enough without removing partial saves.
- `#37` upcoming-slate lock detection stays as-is.

---

## 11. Attachments and References

No ticket attachments. References:

- `docs/PRDs/PRD-11-incomplete-submit-and-admin-lock-copy.md`
- `march-madness-frontend/src/pages/Picks.jsx` (`computeSubmitWarnings`, incomplete Modal)
- `march-madness-frontend/src/pages/AdminUserPicks.jsx`
- PRs #36, #37 (context only)
