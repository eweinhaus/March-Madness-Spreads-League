# CRITICAL SECURITY FINDINGS - Spread Pools Production

**Audit Date:** 2026-08-23  
**Production URL:** https://spread-league-api.vercel.app  
**Status:** 🚨 **CRITICAL P0 VULNERABILITY CONFIRMED**

---

## 🚨 P0: Unauthenticated Score Update Endpoint (PRODUCTION EXPLOIT)

**Severity:** CRITICAL P0 - EXPLOITABLE NOW  
**File:** `march_madness_backend/main.py` line 1016-1029  
**Status:** ✅ FIXED IN THIS PR

### The Vulnerability

`POST /update_score` has **NO authentication check**. Any unauthenticated user can manipulate game results and leaderboard scores.

```python
@app.post("/update_score")
def update_score(result: GameResult):  # ← NO AUTH!
    db = get_db()
    game_ref = db.collection("games").document(result.game_id)
    game_snap = game_ref.get()
    if not game_snap.exists:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game_ref.update({"winning_team": result.winning_team})  # ← WRITES TO DB
    _affected, deltas = update_game_scores(db, result.game_id, result.winning_team)
    apply_leaderboard_point_deltas(db, deltas)
    invalidate_leaderboard_and_stats(db)
```

### Confirmed on Production

```bash
curl -X POST "https://spread-league-api.vercel.app/update_score" \
  -H "Content-Type: application/json" \
  -d '{"game_id": "fake123", "winning_team": "Duke"}'

# Response: {"detail": "Game not found"}
# ❌ Should return 401 Unauthorized (no Bearer token)
# ❌ Already queried Firestore to check game existence
```

With a real `game_id` (obtainable from public leaderboard), an attacker can:
1. Set any game's `winning_team`
2. Rescore all user picks
3. Manipulate leaderboard standings
4. Affect prizes in this 40+ user competition

### Impact

- **Competition Integrity:** Complete compromise
- **User Trust:** Players' picks can be scored incorrectly
- **Financial:** Real money/prizes affected
- **Exploitability:** Trivial (single curl command)

### The Fix

Add admin authentication (same as `PUT /games/{game_id}`):

```python
@app.post("/update_score")
async def update_score(result: GameResult, current_user: User = Depends(get_current_admin_user)):
    # Now requires Firebase ID token + admin: true in user doc
    db = get_db()
    # ... rest unchanged
```

**Applied in this PR:** ✅ One line change, zero breaking changes

---

## P1: Unauthenticated Pick Data Leaks

### P1-001: GET /user_picks/{uid} - No Auth Required

**File:** `march_madness_backend/main.py` line 1182-1218  
**Status:** Documented (not fixed in emergency PR)

Returns full pick history for any user by UID. UIDs are public via leaderboard.

**Current behavior:**
- Filters to started games only (line 1196: `gd <= current_time`)
- Intentional per code comments ("for started games")
- Does NOT hide lock status

**Concern:** Leaks competitive intel (who picked what, including locks)

**Recommendation:** 
- Require authentication OR
- Hide `lock` field unless current_user = requested uid OR
- Product decision: are public picks post-lock the intended design?

### P1-002: GET /user_all_past_picks/{uid} - No Auth Required

**File:** `march_madness_backend/main.py` line 1546-1632  
**Status:** Documented

Similar to P1-001 but includes tiebreaker picks and accuracy diffs.

### P1-003: GET /tiebreakers Returns HTTP 500

**File:** `march_madness_backend/main.py` line 1661-1670  
**Status:** Documented (Firestore index issue)

```python
@app.get("/tiebreakers")
def get_tiebreakers():
    result = []
    for doc in db.collection("tiebreakers") \
        .where("start_time", ">", current_time) \
        .where("is_active", "==", True) \
        .order_by("start_time").stream():  # ← COMPOSITE INDEX REQUIRED
```

**Error:** `FAILED_PRECONDITION: The query requires an index`

**Fix:** Create Firestore composite index:
```json
{
  "collectionGroup": "tiebreakers",
  "queryScope": "COLLECTION",
  "fields": [
    {"fieldPath": "is_active", "order": "ASCENDING"},
    {"fieldPath": "start_time", "order": "ASCENDING"}
  ]
}
```

OR simplify query (fetch all active, filter in-memory like line 1100-1114).

### P1-004: Production API Behind GitHub Main

**Status:** Deployment lag

`GET /app-config` exists in main after today's football PRD merge but returns 404 on production. Frontend may be using stale sport mode logic.

---

## P2: Public API Information Disclosure

### P2-001: /docs and /openapi.json Public

**Status:** Low priority (FastAPI default)

Swagger docs expose all endpoint schemas. Not a vulnerability but reveals API surface.

**Recommendation:** Disable in production:
```python
app = FastAPI(docs_url=None, redoc_url=None) if os.getenv("ENV") == "production" else FastAPI()
```

### P2-002: GET /stats/{uid} - Detailed Public History

**Status:** Low priority (may be intentional)

Returns 20 recent picks, streaks, favorite teams, best/worst games. No auth required.

### P2-003: GET /leaderboard - UIDs Exposed

**Status:** Low priority (required for pick lookup)

Firebase UIDs in leaderboard response enable P1-001/P1-002 lookups. This may be intentional design.

---

## Summary for Emergency PR

**This PR fixes:** P0-001 only (unauthenticated score update)

**Not fixed (documented for follow-up):**
- P1-001, P1-002: Public pick data (product decision needed)
- P1-003: Tiebreaker index (Firestore config)
- P1-004: Deployment lag (ops issue)
- P2-001, P2-002, P2-003: Public API surface (low priority)

**Recommendation:** Merge this PR immediately, deploy to production ASAP, then address P1 items in follow-up PRs.
