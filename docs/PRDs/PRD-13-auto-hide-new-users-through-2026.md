# PRD-13: Auto-Hide New Users Through 2026-12-31

## 1. Problem Statement and Context

### What
On **new** Firestore user create, if the create happens on or before **2026-12-31** (America/New_York calendar day, inclusive), set `hidden: true` by default so accidental wrong Google logins stay off the public leaderboard / stats / live lists / admin user lists until Ethan explicitly unhides them.

After that date, new creates must **not** auto-hide (return to today's visible default).

### Background
PRD-10 added `users.hidden` + `user_is_listed`. Ethan and Herbie are admin+hidden; wrong duplicate Jarin login (`jarinhanika01@gmail.com`) was manually hidden. Accidental second Google accounts keep appearing on the board. Temporary default-hide for all new signups through end of 2026 reduces that class of support tickets.

Today's create path in `get_current_user` writes:

```python
new_user = {
    "uid": uid,
    "email": email,
    "display_name": display_name,
    "league_id": LEAGUE_ID,
    "make_picks": True,
    "admin": False,
    "created_at": server_timestamp(),
}
```

`hidden` is omitted (treated as false). Existing users are never rewritten on login.

### Related Work
- [PRD-10](./PRD-10-admin-and-hidden-users.md) — `hidden` flag, `user_is_listed`, `scripts/make_admin.py --hidden` / `--no-hidden`
- `get_current_user` create branch in `march_madness_backend/main.py`
- Cache invalidate already runs on create (`invalidate_leaderboard_and_stats`)

### Out of scope
- Changing listing filters (`user_is_listed` stays as in PRD-10)
- Auto-unhide on picks, admin tools, or second sign-in
- Backfilling / rewriting existing users
- Deleting wrong accounts (hide only)
- Frontend "request unhide" UI
- Season wipe

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Why |
|------|-----|
| `march_madness_backend/main.py` | `get_current_user` new-user create; return `User(..., hidden=...)` |
| `march_madness_backend/auth.py` | `User.hidden` already exists |
| `scripts/make_admin.py` | Official unhide path: `--no-hidden` |
| `docs/ARCHITECTURE.md` / `docs/LOCAL_DEV.md` | Note temporary auto-hide window if those docs mention user create |
| Tests near PRD-10 hidden coverage | Create-with-auto-hide cases |

### Similar Implementations
- PRD-10: missing `hidden` ⇒ listed; `hidden: true` ⇒ omitted from lists; picks still allowed if `make_picks`.
- `make_admin.py --no-hidden` already clears the flag and invalidates caches.

### Architecture Notes
- Only the **create** branch changes. If `user_snap.exists`, do not touch `hidden`.
- Timezone for the cutoff: **America/New_York** (league / product owner TZ). Inclusive through end of 2026-12-31 ET ⇒ auto-hide when local date `<= 2026-12-31`; starting `2027-01-01 00:00:00 America/New_York`, do not set auto-hide.
- Prefer a named constant / helper so the date is obvious in code review, e.g. `AUTO_HIDE_NEW_USERS_THROUGH = date(2026, 12, 31)`.

### Database/API Context
No schema change beyond writing `hidden: true` on create during the window. Unhide remains a Firestore field flip via CLI.

---

## 3. Design Decisions (Pre-Made)

### Approach
1. Add helper (concept):

```python
from datetime import date
from zoneinfo import ZoneInfo

AUTO_HIDE_NEW_USERS_THROUGH = date(2026, 12, 31)  # inclusive, America/New_York

def new_user_should_auto_hide(now_utc: datetime | None = None) -> bool:
    now = now_utc or datetime.now(timezone.utc)
    local_day = now.astimezone(ZoneInfo("America/New_York")).date()
    return local_day <= AUTO_HIDE_NEW_USERS_THROUGH
```

2. On create in `get_current_user`:

```python
auto_hidden = new_user_should_auto_hide()
new_user = {
    ...
    "admin": False,
    "hidden": auto_hidden,  # True through 2026-12-31 ET; False afterward
    "created_at": server_timestamp(),
}
user_ref.set(new_user)
...
return User(..., admin=False, hidden=auto_hidden, make_picks=True)
```

3. After 2026-12-31 ET: `hidden: False` (or omit field — prefer explicit `False` for clarity on new docs).
4. **No** auto-unhide anywhere else (submit_pick, login, admin routes).
5. Operators unhide with existing CLI, e.g.:

```bash
python scripts/make_admin.py --name "Real Display Name" --no-hidden
# or
python scripts/make_admin.py --uid <firebase-uid> --no-hidden
```

6. Keep `invalidate_leaderboard_and_stats` on create (already present). Optionally also invalidate live cache if create does not already — match existing create behavior; do not invent a new wipe.

### Rationale
- Default-hide stops wrong logins from polluting the board immediately.
- Hard end date avoids permanent "invisible league" after the season window Ethan chose.
- Explicit CLI unhide matches how Ethan/Herbie/Jarin were managed.

### Patterns/Libraries
- Existing `zoneinfo` / UTC helpers already used in backend scoring/week bounds.
- Existing `User.hidden` + `user_is_listed`.

### Code Organization
- Helper next to `user_is_listed` / auth section in `main.py` (or tiny module if tests prefer pure function import).

---

## 4. Implementation Guidance

### Step-by-step Plan
1. Add `new_user_should_auto_hide` + constant.
2. Wire create dict + returned `User` to set `hidden` from that helper.
3. Unit-test helper around ET midnight boundaries (2026-12-31 23:59 ET → True; 2027-01-01 00:00 ET → False).
4. Unit/integration: create path writes `hidden: true` when helper True; existing user login does not flip hidden.
5. Doc note in LOCAL_DEV / ARCHITECTURE one liner if those mention user flags.
6. Deploy API; no Firestore backfill.

### Key Functions/Methods
- `new_user_should_auto_hide`
- `get_current_user` create branch
- `scripts/make_admin.py --no-hidden` (unchanged, document as unhide)

### Data Flow
First Google sign-in → token verify → no user doc → create with `hidden=true` (during window) → caches invalidate → user can pick/admin if flagged, but never appears on lists until `--no-hidden`.

### Complex Logic Breakdown
**Inclusive end-of-day ET:** compare **dates** in America/New_York, not a UTC midnight cutoff, so "through 2026-12-31" matches owner language.

**Existing wrong accounts:** already hidden manually; this PRD does not re-scan Auth.

### Code Examples
See Approach section.

---

## 5. Edge Cases and Error Handling

### Edge Cases
- User created during window with `hidden: true`, then `--no-hidden` → stays visible forever (later logins must not re-hide).
- User created after window → `hidden: false`; later code deploys must not hide them on login.
- Clock skew: use server UTC → convert to ET date (same as other league time logic).
- Admin create during window: still auto-hidden unless separately promoted; promoting admin does **not** imply unhide (PRD-10 kept those independent — Jared admin visible; Ethan admin+hidden).

### Error Scenarios
- CLI unhide still requires user doc exists (unchanged).

### Validation Requirements
- Create must not set `make_picks: false` to hide (forbidden — blocks picks).

### Error Messages
- No user-facing "you are hidden" banner required in this PRD.

---

## 6. Likely Pitfalls to Avoid

### Common Mistakes
- Updating `hidden` on every login for existing users.
- Using UTC date only and cutting off early evening ET on Dec 31.
- Auto-unhide when they submit a pick.
- Hardcoding display names of wrong accounts.
- Forgetting to pass `hidden=auto_hidden` on the returned `User` after create (today's create return omits `hidden`).

### Gotchas
- Leaderboard cache: create already invalidates; confirm prod sees new hidden users omitted.
- After Jan 1 2027, leave the helper in place returning False (or delete later in a cleanup PR) — do not leave a permanent True.

### Performance Concerns
- None.

### Security Considerations
- Hidden users still authenticate; do not leak via 403 on by-uid routes (keep PRD-10 404 behavior).

### Integration Issues
- Ops runbook: real players who sign up during the window need `make_admin.py --no-hidden` (and `--admin` only if intended).

---

## 7. Testing Requirements

### Test Scenarios
1. `new_user_should_auto_hide` True for 2026-12-31 23:30 ET; False for 2027-01-01 00:00 ET.
2. Create when True → Firestore `hidden is True`; returned User.hidden True.
3. Create when False → `hidden is False` (or omitted equivalent listed).
4. Existing user with `hidden: false` logs in → field unchanged.
5. Existing user with `hidden: true` logs in → stays true.
6. Hidden new user still passes `make_picks` submit permission check.

### Unit Tests
- Pure date helper with frozen `now_utc`.
- Create-path test with mocked Firestore set payload asserting `hidden` key.

### Manual Testing
- Staging/prod: create throwaway Google account during window → absent from `/leaderboard` and `/stats`; `--no-hidden` → appears after cache invalidate.

### Test Data
- Fake uids; do not use real player accounts.

---

## 8. Acceptance Criteria

### Functional Requirements
- [ ] New users created through 2026-12-31 America/New_York inclusive get `hidden: true` at create.
- [ ] New users created on/after 2027-01-01 America/New_York do not auto-hide.
- [ ] Existing user documents are never auto-modified by this feature on login.
- [ ] No auto-unhide except explicit CLI/DB flip (`make_admin.py --no-hidden` or equivalent).
- [ ] Hidden behavior remains PRD-10 (lists/404s); picks still allowed when `make_picks`.
- [ ] Create return path includes `hidden` on `User`.

### User-Facing Behavior
- Accidental new Google accounts stay off the public board until Ethan unhides.
- Legitimate new players need an explicit unhide during the window.

### Performance Requirements
- No new indexes.

### Security Requirements
- Keep 404 (not 403) for hidden by-uid public routes.

---

## 9. Dependencies and Considerations

### External Services
- None new.

### Database Changes
- Write-time only on create.

### Configuration
- Optional: env override for tests (`AUTO_HIDE_NEW_USERS_THROUGH=YYYY-MM-DD`) — **not required**; constant is fine unless tests need injection (prefer function arg `now_utc`).

### Breaking Changes
- During the window, every brand-new signup is invisible until unhidden (intentional).

### Migration Steps
1. Merge + deploy API.
2. No backfill.
3. When a real player signs up during the window: `python scripts/make_admin.py --uid <uid> --no-hidden` (plus `--admin` only if needed).

---

## 10. Project Notes from Ticket

### Important Notes
- Product owner: Ethan Weinhaus via Orchestrator (2026-09-09).
- Triggered after hiding wrong Jarin duplicate login.
- Locked decisions: create-time auto-hide ≤ 2026-12-31; existing unchanged; unhide only explicit; after Dec 31 2026 no auto-hide.

### Assumptions
- "Created from now through 2026-12-31" means create timestamp's **ET calendar date**, inclusive.
- Repo: `eweinhaus/March-Madness-Spreads-League` (Spread Pools).

---

## 11. Attachments and References

- `docs/PRDs/PRD-13-auto-hide-new-users-through-2026.md`
- `docs/PRDs/PRD-10-admin-and-hidden-users.md`
- `scripts/make_admin.py`
