# QA Audit Summary - Spread Pools

**Date:** 2026-08-23  
**Production:** https://www.spreadpools.com (https://spread-league-api.vercel.app)  
**Status:** P0+P1 fixes completed in PR #22

---

## Issues Fixed

### P0 (CRITICAL) - Fixed in PR #22 ✅

1. **Frontend Crash** - `SHOW_LOCK_OF_THE_DAY_UI` undefined
   - **Impact:** Save Picks button crashes on main
   - **Fix:** Replaced with `showLockUI` (already defined)
   - **File:** `march-madness-frontend/src/pages/Picks.jsx` lines 374, 565, 584

2. **Security Exploit** - `POST /update_score` no authentication
   - **Impact:** Any user can manipulate game results and leaderboard
   - **Fix:** Added `Depends(get_current_admin_user)`
   - **File:** `march_madness_backend/main.py` line 1017

### P1 (HIGH) - Fixed in PR #22 ✅

3. **Pick Leak** - `GET /live_games/{game_id}/picks` before kickoff
   - **Impact:** Exposes picks before game starts
   - **Fix:** Returns 403 if `game_date > current_time`

4. **Pick Leak** - `GET /live_tiebreakers/{tiebreaker_id}/picks` before start
   - **Impact:** Exposes tiebreaker answers before reveal
   - **Fix:** Returns 403 if `start_time > current_time`

5. **Pick Leak** - `GET /stats/{uid}` includes future picks
   - **Impact:** Exposes `picked_team` and `lock` for unstarted games
   - **Fix:** Filters `recent_picks` to `game_date <= current_time`

6. **500 Error** - `GET /tiebreakers` missing Firestore index
   - **Impact:** Endpoint returns 500 on production
   - **Fix:** Changed to fetch-all + in-memory filter (matches `/picks_data` pattern)

---

## Configuration Notes

### SPORT_MODE vs LEAGUE_ID Default Mismatch

**Observation:** Configuration defaults are misaligned:
- `SPORT_MODE` defaults to `"football"` (sport_config.py line 34)
- `LEAGUE_ID` defaults to `"march_madness_2025"` (sport_config.py line 126, main.py line 48)

**Impact:** Low - production sets both explicitly via Vercel env vars

**Recommendation:** For consistency, consider:
```python
# Option 1: Both default to current season
SPORT_MODE default: "football"
LEAGUE_ID default: "football_2026"

# Option 2: Keep MM as fallback for both
SPORT_MODE default: "march_madness"  
LEAGUE_ID default: "march_madness_2025"
```

Or add validation warning when SPORT_MODE and LEAGUE_ID don't match.

### get_week_bounds DST Behavior

**Observation:** Football week boundaries use `timedelta(weeks=1)` which always adds exactly 168 hours UTC (7 days). During DST transitions:
- Fall back (Nov 1, 2026): One week in ET is 169 hours UTC (25-hour Sunday)
- Spring forward: One week in ET is 167 hours UTC (23-hour Sunday)

**Current Implementation:**
```python
def get_week_bounds(dt_utc):
    # Find most recent Wednesday 00:00 ET
    start_ny = datetime(..., tzinfo=ZoneInfo("America/New_York"))
    end_ny = start_ny + timedelta(weeks=1)  # ← Always 168h UTC
    return start_ny.astimezone(timezone.utc), end_ny.astimezone(timezone.utc)
```

**Impact:** During DST week (Oct 28 - Nov 4, 2026):
- Week start: Wed Oct 28, 00:00 ET = 04:00 UTC (EDT, UTC-4)
- Week end: Wed Nov 4, 00:00 ET = 05:00 UTC (EST, UTC-5)
- UTC duration: 169 hours (not 168)

**Analysis:** The implementation is **CORRECT** because:
1. ZoneInfo handles DST transitions automatically
2. `start_ny + timedelta(weeks=1)` creates Wed Nov 4, 00:00 ET (not 169h later)
3. Tests confirm boundary alignment (test_week_bounds_dst_transition)

**Conclusion:** No bug. The 1-hour UTC gap is expected and properly handled.

### Admin has_current_day_lock Still Uses Day Bounds

**File:** `march_madness_backend/main.py` line 1374

**Issue:** Documented in PR #20 (QA findings), not fixed in P0/P1 batch:

```python
@app.get("/admin/user_picks_status")
async def get_user_picks_status(...):
    current_day_start, current_day_end = get_lock_day_bounds(current_time)  # ← Always day
    
    # Later checks if lock is in [day_start, day_end)
    # Should use get_week_bounds() in football mode
```

**Impact:** Admin dashboard shows incorrect lock status in football mode. A lock from Monday won't show as "current week lock" on Tuesday.

**Status:** Documented for follow-up PR (requires product decision on admin workflow)

---

## Security Assessment

### ✅ Good Security Practices

- **Authentication:** Firebase ID token verification on all authenticated routes
- **Authorization:** Admin routes properly gated with `admin: true` check
- **Firestore Rules:** Deny all client access (backend-only via Admin SDK)
- **CORS:** Properly restricted origins
- **CRON_SECRET:** 16+ char minimum, constant-time comparison

### Public Endpoints (Intentional)

Per user confirmation, these are **by design**:
- `GET /user_picks/{uid}` - Public picks for started games
- `GET /user_all_past_picks/{uid}` - Public history for started games
- `GET /leaderboard` - Includes UIDs (enables above lookups)
- `GET /stats/{uid}` - Public detailed stats (now filters future picks)

All properly filter to `game_date <= current_time` after PR #22.

---

## Test Coverage

### ✅ Strong Coverage
- Scoring logic (test_scoring.py)
- Week boundaries + DST (test_football_weeks.py)
- Leaderboard ranking (test_leaderboard_ranking.py)
- Sport config (test_sport_config.py)

### ⚠️ Missing Coverage
- Admin endpoints (no tests for `/admin/user_picks_status`)
- Pick leak edge cases (before/after kickoff)
- Concurrent lock updates (race conditions)
- Tiebreaker validation

---

## Related PRs

- **PR #20** - Original QA audit + unreachable code fix
- **PR #21** - Emergency P0 fix (update_score auth only, superseded by #22)
- **PR #22** - Complete P0+P1 batch fix (MERGED)

---

## Recommendations

### Immediate (Post-PR #22)
1. Deploy to production ASAP
2. Monitor logs for unauthorized access attempts
3. Verify admin UI still works (score updates)

### Short Term
1. Fix admin lock tracking for football mode (HIGH-001 from original audit)
2. Add integration tests for admin endpoints
3. Consider adding composite index for `/tiebreakers` if collection grows

### Long Term
1. Align SPORT_MODE and LEAGUE_ID defaults
2. Add tiebreaker type validation (numeric vs text)
3. Transaction safety for concurrent lock updates
4. Document public endpoint design decisions
