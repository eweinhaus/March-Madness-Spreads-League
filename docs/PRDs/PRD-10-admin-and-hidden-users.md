# PRD-10: Admin Flags + Hidden Users

## 1. Problem Statement and Context

### What
Promote three existing Firebase users to admin, and hide two of them from every player-facing and admin-facing user list, while they can still log in, submit picks, and use admin tools.

Target users (production `users` collection, live as of 2026-08-24):

| Display name (Firestore `display_name`) | UID | `admin` | `hidden` |
|---|---|---|---|
| Ethan Weinhaus | `xc7KvlCV8oN4R3STgRVrBEmuJbq1` | `true` | `true` |
| Herbie Husker | `k3ra7epCMXNdOvxY9MUIhJGARfH2` | `true` | `true` |
| jared Luebbe | `yJONBUizmvPyvTMyVPzb4OMo7fa2` | `true` | leave unset / `false` |

Jared stays fully visible and competing. Only Ethan and Herbie disappear from lists.

### Background
Spread Pools (`spreadpools.com`) is an against-the-spread pick pool. Auth is Firebase Google OAuth. App profiles live in Firestore `users/{uid}` with `admin: bool` (default `false`) and `make_picks: bool` (default `true`). Admin routes use `Depends(get_current_admin_user)` which checks `current_user.admin`. Leaderboard, stats, live pick lists, and admin user-picks all query `users.where("make_picks", "==", True)`.

After the football_2026 season reset, new users are created with `admin: False`. Public APIs do not expose the admin flag; assume nobody is admin until this PRD runs. `scripts/make_admin.py` already sets `admin: True` by UID.

Hiding cannot be `make_picks: False`. That flag also 403s `POST /submit_pick` and `POST /tiebreaker_picks`. Product decision: hidden users still play (picks persist and score) and still use admin tools; they must never appear on leaderboard, stats, live pick lists, or admin user lists.

### Related Work
- `scripts/make_admin.py` — existing Admin SDK CLI for `admin: True`
- `get_current_admin_user` in `march_madness_backend/main.py`
- PRD-05 admin user-picks status (`GET /admin/user_picks_status`)
- PRD-07 stats restore (`GET /stats`, `GET /stats/{uid}`)
- Do **not** run `scripts/reset_season.py`

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Why |
|------|-----|
| `scripts/make_admin.py` | Extend into the flags CLI (admin + hidden, UID or display name) |
| `march_madness_backend/auth.py` | `User` model: add `hidden: bool = False` |
| `march_madness_backend/main.py` | Read `hidden` in `get_current_user`; listing queries; 404-by-uid routes; live pick counts; stats consensus loop |
| `march_madness_backend/tests/` | New tests for listed-user helper + listing filters |
| `docs/ARCHITECTURE.md` | Document `hidden` on `users` |
| `docs/LOCAL_DEV.md` | Update `make_admin.py` usage from UID-only to `--uid` / `--name` |
| Frontend list pages | No hardcoded names; they consume APIs. Verify they do not merge extra user directories. |
| `march-madness-frontend/src/pages/Leaderboard.jsx` | Renders `/leaderboard` |
| `march-madness-frontend/src/pages/Stats.jsx` | Renders `/stats` |
| `march-madness-frontend/src/pages/AdminUserPicks.jsx` | Renders `/admin/user_picks_status`; "Copy all user emails" button uses that endpoint's user list |
| `march-madness-frontend/src/pages/Live.jsx` | Live pick totals + per-game pick names |

### Similar Implementations
- `admin` is a Firestore boolean, default false, set by CLI, read in `get_current_user`.
- `make_picks` is the existing "exclude from lists AND block picks" flag. Copy its list-filter pattern, but **do not** reuse it for hiding.
- Direct-by-uid routes already 404 when `make_picks` is false (`GET /admin/user_all_picks/{uid}`, `GET /user_all_past_picks/{uid}`). Apply the same 404 to hidden users, including `GET /stats/{uid}` and `GET /user_picks/{uid}` which currently only check existence.

### Architecture Notes
- Firestore rules deny all client access. Only the backend Admin SDK reads/writes `users`.
- Do **not** migrate off Firebase/Vercel.
- Do **not** hardcode these three display names or UIDs in application code. Flags on the user document are the source of truth so future hidden admins do not need a code change.
- Leaderboard and stats are cached (`_cache` collection). After flipping flags, call `invalidate_leaderboard_and_stats(db)` (and live cache).
- Stay on the existing Python Admin SDK script pattern. Do not introduce a separate Firebase CLI workflow; `make_admin.py` is already the team's Firestore CLI.

### Database/API Context
New optional field on `users/{uid}`:

```
hidden: bool   # default false / missing. True = omit from all user lists and public-by-uid views
```

No new collections. No Firebase Auth custom claims. Admin remains `users.admin`, not a custom claim.

`GET /users/me` may include `hidden` for the signed-in user (harmless). Do not use it to hide the nav "Games / User Picks" admin links — those stay gated on `admin`.

---

## 3. Design Decisions (Pre-Made)

### Approach
1. Add `hidden: bool = False` on `User` in `auth.py`. `get_current_user` reads `user_data.get("hidden", False)`. New-user create dict may omit it (missing = false) or set `hidden: False`; either is fine. Do **not** set `hidden: False` as a required write on every login.
2. Add a single helper in `main.py` and use it everywhere a user would be listed or fetched for public/admin display:

```python
def user_is_listed(u: dict) -> bool:
    """True if this user belongs on leaderboard, stats, live pick lists, and admin user lists."""
    if not u:
        return False
    if not u.get("make_picks", True):
        return False
    if u.get("hidden"):
        return False
    return True
```

Replace every `if not u.get("make_picks"): continue` (and equivalent) with `if not user_is_listed(u): continue`. For collection scans that today do `users.where("make_picks", "==", True)`, keep that query (cheap) **and** skip docs where `hidden` is true in Python. Do **not** add a Firestore composite query on `(make_picks, hidden)` — extra index for ~15 users is not worth it. Do **not** query `hidden == False` only: missing `hidden` must still list.
3. Direct-by-uid GET routes that reveal a user's picks/stats: if the target is not `user_is_listed`, return **404** `User not found` (same as missing / `make_picks` false). Do not 403 (that confirms the uid exists).
4. Hidden users **keep** `make_picks: True`. `POST /submit_pick` and `POST /tiebreaker_picks` stay allowed. Scoring, lock-swap, and admin game/score endpoints stay allowed when `admin` is true.
5. Live pick **counts** (`home_picks` / `away_picks` / `total_picks` on `/live`) exclude hidden users, same as names. Otherwise a ghost vote still "appears."
6. Extend `scripts/make_admin.py` (keep the filename; it is already in docs) so it can set `admin` and/or `hidden` by `--uid` or `--name` (case-insensitive `display_name` match). After a successful update, invalidate leaderboard, stats, and live caches. Print the resulting flags.
7. Production data step (required to close this PRD, not just code): run the script against prod so the three rows above match the table. Lookup by `--name` is preferred; UIDs above are the 2026-08-24 snapshot in case names collide.

### Rationale
- A new `hidden` flag matches how `admin` already works and does not break picking.
- Filtering in the backend is mandatory: Firestore is deny-all to clients, so lists only exist via API. Frontend does not need name denylists.
- 404 on by-uid routes prevents leaking a hidden user via Leaderboard/Stats deep links.
- CLI over Firebase Console so it is repeatable after a future season wipe.

### Patterns/Libraries
- Existing `firebase_admin` + Firestore in `scripts/make_admin.py`
- Existing `invalidate_leaderboard_and_stats` / `invalidate_live_cache`

### Code Organization
- Helper `user_is_listed` next to `get_current_admin_user` in `main.py`.
- Keep listing logic in the backend; no new frontend feature flag.

---

## 4. Implementation Guidance

### Step-by-step Plan
1. Add `hidden` to `User` and `get_current_user`.
2. Add `user_is_listed` and switch every list/filter site listed below.
3. Add 404 checks on by-uid GET routes that still only check `exists`.
4. Extend `scripts/make_admin.py` CLI.
5. Tests for helper + listing + submit-still-works + admin-still-works.
6. One-line `users` field note in `docs/ARCHITECTURE.md`.
7. Update `docs/LOCAL_DEV.md` to reflect new CLI usage (`--uid` / `--name`, not just UID or email).
8. Deploy API, then run the script on production for the three users. Confirm caches rebuild without those two names.

### Key Functions/Methods
- `user_is_listed(u: dict) -> bool`
- `get_current_user` — pass `hidden` through
- `scripts/make_admin.py` — argparse: `--uid` or `--name` (exactly one), `--admin` / `--no-admin`, `--hidden` / `--no-hidden`. At least one flag required. `--name` scans `users` and errors if 0 or >1 case-insensitive matches.
- Reuse cache invalidation helpers after CLI writes.

### Data Flow
1. CLI updates `users/{uid}` fields via Admin SDK.
2. CLI invalidates `_cache` leaderboard/stats/live docs.
3. Next `/leaderboard`, `/stats`, `/live` recompute from `users` and omit `hidden`.
4. Hidden user signs in → `get_current_user` returns `admin=True, hidden=True, make_picks=True` → can pick and open `/admin/*` → does not appear in other people's lists.

### Complex Logic Breakdown
**Listed vs playable vs admin are independent:**

| | `make_picks` | `hidden` | `admin` | Can pick? | On lists? | Admin UI? |
|---|---|---|---|---|---|---|
| Normal player | true | false | false | yes | yes | no |
| Jared | true | false | true | yes | yes | yes |
| Ethan / Herbie | true | true | true | yes | no | yes |
| Spectator (existing) | false | any | any | no | no | if admin |

Do not invent other combinations in this PRD.

**Collection query:** keep `.where("make_picks", "==", True)` then skip `hidden` in Python. Firestore `== False` would drop documents that omit the field.

### Code Examples
Today (`_compute_and_store_leaderboard_cache`):

```python
for doc in db.collection("users").where("make_picks", "==", True).stream():
    u = doc.to_dict() or {}
    u["uid"] = u.get("uid") or doc.id
    users[u["uid"]] = u
```

Required:

```python
for doc in db.collection("users").where("make_picks", "==", True).stream():
    u = doc.to_dict() or {}
    u["uid"] = u.get("uid") or doc.id
    if not user_is_listed(u):
        continue
    users[u["uid"]] = u
```

CLI usage after this PRD:

```bash
python scripts/make_admin.py --name "Ethan Weinhaus" --admin --hidden
python scripts/make_admin.py --name "Herbie Husker" --admin --hidden
python scripts/make_admin.py --name "jared Luebbe" --admin
```

Keep backward compatibility: `python scripts/make_admin.py <uid>` still means `--uid <uid> --admin`.

### Surfaces that must use `user_is_listed`
Backend (search `make_picks` in `main.py`; this list is the checklist):

- `_compute_and_store_leaderboard_cache`
- `_compute_live_data` (`make_picks_uids` used for live counts)
- `GET /live_games/{game_id}/picks` (display names)
- `GET /admin/user_picks_status`
- `GET /admin/user_all_picks/{uid}` → 404 if not listed
- `GET /user_picks/{uid}` → 404 if not listed
- `GET /user_all_past_picks/{uid}` → 404 if not listed
- live/tiebreaker pick listing around `GET` game/TB pick names (`if not u.get("make_picks")`)
- `_compute_player_stats_list` / `GET /stats`
- `GET /stats/{uid}` → 404 if not listed (today only checks exists)
- **`GET /stats/{uid}` consensus loop** in `get_player_detailed_stats`: when streaming ALL user picks for `all_picks_for_consensus` / `consensus_count` / `against_count`, skip users where `not user_is_listed(u)`. Otherwise hidden users still move consensus percentages on other players' stats pages.

Grep for `make_picks` and `collection("users")` after edits; any list that still uses only `make_picks` is a bug.

Frontend: no denylist. Confirm Leaderboard/Stats/Live/AdminUserPicks/UserPicksModal have no local user directory. Own display name in the navbar is fine (that is the signed-in user, not a list).

**Admin email blast**: `AdminUserPicks.jsx` has a "Copy all user emails" button that uses the user list from `GET /admin/user_picks_status`. Filtering that endpoint with `user_is_listed` is sufficient — do not add a second client-side email filter. Hidden admins will not appear in the copied email list.

---

## 5. Edge Cases and Error Handling

### Edge Cases
- `hidden` field missing → treat as false (listed).
- Display name `jared Luebbe` is lowercase j. `--name` match is case-insensitive; prefer exact UID if two users somehow share a name.
- Hidden user opens `/leaderboard` or `/stats` — they do not see themselves. That is correct.
- Hidden user opens `/admin/user-picks` — they do not see themselves or Herbie. They still see Jared and everyone else.
- Someone bookmarks `/stats/{ethanUid}` — 404.
- Season wipe recreates user docs on next login with `admin: False` and no `hidden`. Re-run the CLI. Do not bake names into app code.
- `make_picks: False` still wins: not listed, cannot pick, even if `hidden` is false.
- **Legacy cutoff stays**: Leaderboard and stats already skip `created_at < 2025-06-01`. Leave that filter as-is; it is independent of `hidden`. Do not remove or modify the legacy cutoff logic.

### Error Scenarios
- CLI `--name` matches 0 users: exit 1, tell operator the user must sign in once.
- CLI `--name` matches >1: exit 1, print UIDs, require `--uid`.
- CLI missing credentials: same error as today (`GOOGLE_APPLICATION_CREDENTIALS` or `FIREBASE_SERVICE_ACCOUNT_JSON`).
- CLI with neither `--uid` nor `--name` and not the legacy positional UID: usage error.

### Validation Requirements
- `hidden` and `admin` are booleans only.
- Do not delete user docs or picks to "hide" someone.

### Error Messages
- By-uid hidden/unlisted: HTTP 404 `{"detail":"User not found"}` (do not say "hidden").
- CLI name miss: `ERROR: No user with display_name matching '...'`.

---

## 6. Likely Pitfalls to Avoid

### Common Mistakes
- Setting `make_picks: False` to hide someone. That blocks picks. Forbidden.
- Hardcoding `Ethan Weinhaus` / `Herbie Husker` in frontend or backend filters.
- Filtering only `/leaderboard` and forgetting `/stats`, live pick names, live counts, and `/admin/user_picks_status`.
- Querying `hidden == False` in Firestore (drops unset fields).
- **Stats consensus leak**: forgetting to filter hidden users from the `all_picks_for_consensus` loop in `get_player_detailed_stats`. Hidden users' picks must not affect consensus percentages on other players' detailed stats pages.

### Gotchas
- Leaderboard/stats/live caches will keep showing hidden users until invalidated. The CLI **must** invalidate. A code-only deploy without a cache bust is not done.
- `GET /stats/{uid}` does not currently check `make_picks`; easy to miss.
- Live totals use a UID set built from `make_picks` users; if you only filter the name list, counts still leak.
- The consensus calculation in detailed stats streams all users and all picks; it is a separate place to apply `user_is_listed`.

### Performance Concerns
- Extra Python skip on ~15 user docs is negligible. Do not add composite indexes.

### Security Considerations
- 404 not 403 on hidden by-uid routes.
- Do not return `hidden` users from admin lists. Product owner asked that admin user-picks hide them too.
- Do not log emails of hidden users in new CLI success lines beyond what `make_admin.py` already prints (`display_name` + uid).

### Integration Issues
- Frontend admin nav is `appUser.admin`. Hidden admins must still get `admin: true` from `/users/me`.
- Do not change lock-swap, scoring, or submit concurrency from PRD-06/08.

---

## 7. Testing Requirements

### Test Scenarios
1. `user_is_listed`: missing hidden + make_picks true → true; hidden true → false; make_picks false → false regardless of hidden.
2. Leaderboard builder omits hidden uid, includes Jared.
3. Stats list omits hidden uid, includes Jared.
4. Admin user_picks_status omits hidden uid, includes Jared.
5. Live pick name list and home/away counts omit hidden users' picks.
6. `GET /stats/{hiddenUid}` and `GET /user_picks/{hiddenUid}` → 404.
7. Stats consensus calculation excludes hidden users from `all_picks_for_consensus`.
8. Hidden user with `make_picks` true can still pass the submit_pick permission check (the `if not current_user.make_picks` branch is **not** taken).
9. `get_current_admin_user` still allows `admin=True, hidden=True`.
10. CLI: mock Firestore, `--name` case-insensitive match updates flags and calls cache invalidate.

### Unit Tests
- `user_is_listed` table.
- Leaderboard/stats helpers with a tiny in-memory user dict (follow `test_prd06_concurrency.py` / `test_stats_correctness.py` style: mock db or extract pure functions).
- Consensus loop filtering (mock user picks, verify hidden user's picks do not contribute to consensus counts).

### Integration Tests
- Not required against real Firebase. Mock streams are enough.

### Manual Testing
After prod CLI:
- Logged-out `/leaderboard` and `/stats`: no Ethan, no Herbie, Jared still there.
- Sign in as Ethan: admin nav visible; Picks save works; leaderboard still has no Ethan.
- Admin User Picks: no Ethan, no Herbie, Jared present.
- Copy all user emails: Ethan and Herbie emails not in clipboard.
- Direct `/stats/<ethanUid>`: 404.
- Open `/stats/<jaredUid>`: verify consensus percentages do not include Ethan/Herbie picks.

### Test Data
- Use the UIDs in the table if hitting prod. For unit tests, fake uids `u_hidden`, `u_jared`, `u_player`.

---

## 8. Acceptance Criteria

### Functional Requirements
- [ ] Ethan Weinhaus and Herbie Husker have `admin: true` and `hidden: true` in prod Firestore.
- [ ] Jared Luebbe (`display_name` `jared Luebbe`) has `admin: true` and is **not** hidden.
- [ ] No other users are changed.
- [ ] `/leaderboard`, `/stats`, `/live` pick names and counts, `/admin/user_picks_status` omit hidden users.
- [ ] By-uid public/admin pick/stats routes 404 for hidden users.
- [ ] Stats consensus calculation excludes hidden users from all players' detailed stats pages.
- [ ] Admin email copy excludes hidden users (via filtered `/admin/user_picks_status`).
- [ ] Hidden users can still `POST /submit_pick` and use admin routes.
- [ ] Jared still appears on leaderboard/stats/admin user-picks.
- [ ] `scripts/make_admin.py` can set admin+hidden by `--uid` or `--name`; legacy `make_admin.py <uid>` still works.
- [ ] Caches are invalidated by the CLI so prod lists update without waiting for TTL.
- [ ] App code has no hardcoded display names/UIDs for this feature.
- [ ] `docs/LOCAL_DEV.md` updated to reflect new CLI usage (not just UID or email).
- [ ] Legacy `created_at < 2025-06-01` cutoff remains unchanged.

### User-Facing Behavior
- Pool members never see Ethan or Herbie on Leaderboard, Stats, Live pick breakdowns, or Admin User Picks.
- Ethan and Herbie can still pick and administer.
- Jared looks like a normal competing admin.
- Consensus percentages on detailed stats pages exclude Ethan and Herbie's picks.
- Admin email copy does not include Ethan or Herbie.

### Performance Requirements
- No new Firestore indexes. No extra full-collection scans beyond today's user stream.

### Security Requirements
- Hidden existence is not confirmed via 403. Admin lists do not include hidden users.

---

## 9. Dependencies and Considerations

### External Services
- Firebase project `spread-league-21126`. Script needs the existing prod service account env (`FIREBASE_SERVICE_ACCOUNT_JSON` or `GOOGLE_APPLICATION_CREDENTIALS`).

### Database Changes
- Additive boolean `hidden` on `users`. No migration job besides the three CLI updates. Existing docs without the field stay listed.

### Configuration
- No new Vercel env vars.

### Breaking Changes
- Legacy `python scripts/make_admin.py <uid>` must keep working.
- Response shapes of leaderboard/stats stay the same; rows are only fewer.

### Migration Steps
1. Merge and deploy **backend** (frontend optional).
2. Run the three CLI commands against prod.
3. Confirm lists. Do not wipe the season.

---

## 10. Project Notes from Ticket

### Important Notes
- Product owner: Ethan Weinhaus. Two jobs in one PRD: (1) make Ethan, Herbie, and Jared admins; (2) hide Ethan and Herbie everywhere lists appear.
- Owner asked for Firebase / CLI. Use the existing Admin SDK script, not a one-off Console click, and not `firebase firestore:set` as a new standard.
- Next PRD number is 10 even though markdown for 04–08 is missing from `docs/PRDs` (those shipped as PRs #26, #28, #29, #30, #32).
- Do not hide anyone else among the 15 current players.
- Do not run `reset_season.py`.

### Assumptions
- After football reset, nobody is currently admin. This PRD is what promotes the three users.
- UIDs in the table match those display names as of 2026-08-24 on `GET /leaderboard`. Re-resolve by name if a wipe happened.
- "Never appear" includes live pick counts, not just names.
- Hidden users' picks still write and still get points in Firestore; those points simply never feed public aggregates.
- `docs/LOCAL_DEV.md` currently says `make_admin.py <firebase-uid-or-email>` but the script is UID-only today. After extending the CLI to support `--uid` / `--name`, update that documentation sentence to match real usage (not email).

---

## 11. Attachments and References

No ticket attachments. References:

- This file: `docs/PRDs/PRD-10-admin-and-hidden-users.md`
- `scripts/make_admin.py`
- `docs/ARCHITECTURE.md` (users collection)
- `docs/LOCAL_DEV.md` (CLI usage)
- Live API: `https://spread-league-api.vercel.app/leaderboard`
