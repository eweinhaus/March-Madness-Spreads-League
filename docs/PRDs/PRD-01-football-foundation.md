# PRD-01: Football Season Foundation (Config, Reset, Branding, Deprecate Cron)

## 1. Problem Statement and Context

### What
Switch the live Spread Pools app from March Madness to the **2026 football season** (NFL + CFB) while keeping basketball code paths selectable via config. Wipe Firestore for a clean season. Update branding/favicon. Deprecate the unused auto-resolve cron pipeline.

### Background
The app is a multi-user **against-the-spread** pick pool (not draft fantasy). It previously ran football (`origin/football_pool`, commit `de5493a`) and later March Madness. Current stack is React + Vite, FastAPI on Vercel, Firestore, Firebase Google Auth. Auto-resolve via GitHub Actions never worked reliably; admins will resolve games manually for this season.

### Related Work
- Follow-on: [PRD-02](./PRD-02-lock-of-the-week-calendar.md) (LOTW + week calendar)
- Follow-on: [PRD-03](./PRD-03-leaderboard-live-football.md) (leaderboard record/TB, Live scrape URLs)
- Historical football scrape: `de5493a` (`college-football` + `nfl` CBS boards)
- Existing wipe/admin tooling: `scripts/make_admin.py`

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Why |
|------|-----|
| `march_madness_backend/main.py` | `LEAGUE_ID`, CBS scrape, `/internal/auto-resolve-games`, week filters |
| `march_madness_backend/scoring.py` | Lock-day helpers (basketball); keep, add football siblings in PRD-02 |
| `march_madness_backend/.env.example` | Document `SPORT_MODE`, drop cron emphasis |
| `march-madness-frontend/src/config.js` | API base URL; extend or add sport config consumer |
| `march-madness-frontend/index.html` | Favicon + title |
| `march-madness-frontend/public/spreads.svg`, `basketball.svg` | Assets |
| `march-madness-frontend/src/pages/Picks.jsx` | Basketball spinner, lock UI flag |
| `march-madness-frontend/src/pages/Home.jsx` | Welcome copy |
| `.github/workflows/auto-resolve-games.yml` | Deprecate |
| `docs/AUTO_RESOLVE.md`, `docs/ARCHITECTURE.md` | Mark cron deprecated |
| `scripts/` | Add season reset script |

### Similar Implementations
- Sport URL switch already done once in `de5493a` (CBS football vs basketball).
- `LEAGUE_ID = os.getenv("LEAGUE_ID", "...")` pattern in `main.py`.

### Architecture Notes
- Firestore rules remain deny-all client access; backend Admin SDK only.
- **Do not** migrate back to Postgres/Render. Stay on Firebase/Vercel.
- Single Firebase project (reuse existing). Full wipe is simpler than a new project.

### Database/API Context
No schema field changes required in this PRD. Reset deletes all documents in season collections. New endpoint:

```http
GET /app-config
```

Unauthenticated or auth-optional; returns sport mode + display strings so frontend does not hardcode sport.

---

## 3. Design Decisions (Pre-Made)

### Approach
1. Introduce **`SPORT_MODE`** env var on the backend: `football` | `march_madness` (default **`football`** for this season).
2. Expose mode via **`GET /app-config`**; frontend reads it once at app load (or on Home/Picks) and branches copy/assets. Optionally mirror with `VITE_SPORT_MODE` only as a build-time fallback if `/app-config` fails — prefer API as source of truth.
3. Set **`LEAGUE_ID=football_2026`** (env). No user-entered league PIN required (keep current Google Auth flow).
4. **Wipe entire Firestore** season data including `users` (per product owner). Same Firebase project.
5. **Deprecate cron**: disable workflow (do not delete file history); leave `/internal/auto-resolve-games` in place but document as unsupported / optional later. Do not spend time fixing scrape-to-grade automation.
6. **Branding**: Product name stays **Spreads**. Subtitle/copy becomes football-season oriented. Replace favicon with a **football-primary** SVG (brown football on dark green circle). When `SPORT_MODE=football`, Picks loading spinner uses football SVG; when `march_madness`, keep basketball SVG.

### Rationale
- Config switch preserves March Madness code for next spring without a big-bang delete.
- Full wipe avoids stale picks/leaderboard cache / old admin flags.
- Cron never worked; admin resolve is enough for v1 (sync button later).

### Patterns/Libraries
- Existing FastAPI + `os.getenv` config.
- Existing Firebase Admin for wipe script.

### Code Organization
- New: `march_madness_backend/sport_config.py` — constants, week calendar stubs used by PRD-02/03, `get_app_config()` dict.
- New: `scripts/reset_season.py` — destructive wipe + confirmation prompt.
- Keep basketball-specific helpers behind `if sport_mode == "march_madness"` or strategy functions in `sport_config.py`.

---

## 4. Implementation Guidance

### Step-by-Step Plan
1. Add `sport_config.py` with `SPORT_MODE`, `LEAGUE_ID`, display name helpers, and `get_app_config()`.
2. Wire `GET /app-config` in `main.py`.
3. Frontend: fetch `/app-config` early (e.g. in `App.jsx` context or `main.jsx`); set document title / show football vs basketball spinner.
4. Create `public/football.svg` favicon; point `index.html` `rel="icon"` at `/football.svg` (or `/spreads.svg` replaced). Keep `basketball.svg` for MM mode spinner.
5. Update Home + nav copy for football season (still “Spreads”).
6. Implement `scripts/reset_season.py`:
   - Require typing `RESET football_2026` to confirm.
   - Delete all docs in: `users`, `games`, `picks`, `tiebreakers`, `tiebreaker_picks`, `leaderboard`, `_cache` (and any other app collections found).
   - Print counts deleted.
7. After wipe: first Google sign-in recreates user docs; promote admins with existing `scripts/make_admin.py`.
8. Deprecate cron:
   - In `.github/workflows/auto-resolve-games.yml`, comment schedule or add `if: false` at job level with a header comment `DEPRECATED — admin resolves manually`.
   - Update `docs/AUTO_RESOLVE.md` and Architecture “Auto-resolve” section: **deprecated for football 2026**.
9. Update `.env.example`: `SPORT_MODE`, `LEAGUE_ID=football_2026`; mark `CRON_SECRET` optional/legacy.

### Key Functions/Methods
```python
# sport_config.py
def get_sport_mode() -> str:  # "football" | "march_madness"
def get_league_id() -> str
def get_app_config() -> dict:
    # { "sport_mode", "league_id", "product_name": "Spreads",
    #   "season_label": "Football 2026", "lock_label": "lock of the week" | "lock of the day" }
```

### Data Flow
```
Env SPORT_MODE ──► sport_config ──► GET /app-config ──► React UI copy/assets
Admin runs reset_season.py ──► Firestore empty ──► users re-register via Google ──► make_admin.py
Admin creates games in Admin UI ──► users pick ──► admin sets winning_team (PRD-03)
```

### Complex Logic Breakdown
None in this PRD beyond safe bulk delete (batch deletes of ≤500 ops per Firestore batch).

### Code Examples
```python
# reset_season.py sketch
COLLECTIONS = ["users", "games", "picks", "tiebreakers", "tiebreaker_picks", "leaderboard", "_cache"]
for name in COLLECTIONS:
    delete_collection(db, name, batch_size=400)
```

---

## 5. Edge Cases and Error Handling

| Case | Handling |
|------|----------|
| `/app-config` fails on frontend | Fall back to `football` defaults for this release; log error |
| Wipe run against wrong project | Script prints project id from credentials; require confirm string |
| Partial wipe failure | Abort and report collection; re-run is idempotent |
| Cron still fires | Job no-ops via `if: false`; endpoint may still exist |

### Validation
- `SPORT_MODE` must be one of the two allowed values; invalid → default `football` + warning log.

### Error Messages
- Reset script: `Refusing to run: confirmation string mismatch`
- Reset script: `Deleted N docs from {collection}`

---

## 6. Likely Pitfalls to Avoid

- **Do not** delete March Madness helper functions; gate them.
- **Do not** change scoring math here (stays 1/2/0 — PRD-02/03).
- **Do not** invent a second Firebase project unless wipe is blocked.
- Forgetting to wipe `_cache` leaves stale leaderboards after new picks.
- Leaving workflow schedule active wastes Actions minutes and may error on secrets.
- Hardcoding football-only strings in 20 files without reading `/app-config` makes spring switch painful.

---

## 7. Testing Requirements

### Unit
- `get_sport_mode` / `get_app_config` with env overrides.

### Manual
- [ ] `/app-config` returns `sport_mode: football`, `league_id: football_2026`
- [ ] Favicon shows football asset in browser tab
- [ ] Home copy reads as football season
- [ ] Dry-run of reset script lists collections; full run empties emulator or staging
- [ ] After wipe + sign-in + `make_admin.py`, admin can open Admin Games
- [ ] Auto-resolve workflow does not run on schedule

### Test Data
- Use Firebase emulator if available; otherwise staging project only — never wipe production without explicit confirm.

---

## 8. Acceptance Criteria

- [ ] `SPORT_MODE=football` is default; basketball paths remain in repo and selectable via env
- [ ] `GET /app-config` documents sport + lock label for UI
- [ ] `LEAGUE_ID` is `football_2026` (or env override)
- [ ] Favicon updated to football-forward SVG; basketball asset retained
- [ ] User-facing rename/copy updated for football where sport-specific (Picks spinner, Home)
- [ ] `scripts/reset_season.py` can wipe all listed collections with confirmation
- [ ] Auto-resolve GitHub workflow is disabled/deprecated; docs updated
- [ ] Password/forgot-password work explicitly **out of scope**

---

## 9. Dependencies and Considerations

### External Services
- Same Firebase + Vercel. CBS scrape changes are PRD-03 (Live page only).

### Database
- Full wipe; no migration of old picks.

### Configuration
```
SPORT_MODE=football
LEAGUE_ID=football_2026
# CRON_SECRET optional / unused for season
```

### Breaking Changes
- All existing users/picks/games gone after reset.
- Cron consumers break by design.

### Migration Steps
1. Deploy code with `SPORT_MODE=football`
2. Run `reset_season.py` against production (owner-approved window)
3. Have intended admins Google sign-in → `make_admin.py <uid>`
4. Admin enters Week 0 games

---

## 10. Project Notes

### Important Notes
- Cron never worked — do not “fix” it in this PRD.
- Include Stats / Admin user-picks / tiebreakers in later PRDs; foundation only enables the switch.
- Season length and week labels are defined in PRD-02.

### Assumptions
- Aug–Dec **2026** calendar (aligned with “week of 8/29” → “week of 12/4”).
- Product owner accepts empty DB and re-invite of all players.
- “Record” ranking semantics defined in PRD-03.

---

## 11. Attachments and References

- Branch reference: `origin/football_pool`
- Commit reference: `de5493a` (football CBS URLs)
- No `./attachments/` folder for this ticket
