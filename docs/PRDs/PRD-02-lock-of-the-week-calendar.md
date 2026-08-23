# PRD-02: Football Week Calendar & Lock of the Week

## 1. Problem Statement and Context

### What
Replace March Madness **lock-of-the-day** (3am–3am ET) and **tournament half** filters with a **15-week Wed→Tue ET calendar** and **one lock of the week (LOTW)**. Re-enable lock UI on the Picks page. Keep pick lock timing at **1 minute before tip**. Keep scoring **1 / 2 / 0**.

### Background
Football historically used `get_game_week_bounds` (Wed 12:00 AM – Tue 11:59 PM EST) on `football_pool`. Current code uses `get_lock_day_bounds` in `scoring.py` + `etLockDay.js`. Owner wants both NFL and CFB on one slate, with labeled weeks from CFB Week 0 through a combined CFB/NFL label.

### Related Work
- Depends on: [PRD-01](./PRD-01-football-foundation.md) (`SPORT_MODE`, `/app-config`)
- Consumed by: [PRD-03](./PRD-03-leaderboard-live-football.md) (leaderboard week filters)
- Historical UI: `origin/football_pool` → `march-madness-frontend/src/pages/Picks.jsx` (`getGameWeekBounds`)

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Role |
|------|------|
| `march_madness_backend/scoring.py` | Add week-bound helpers; keep day-bound helpers for MM |
| `march_madness_backend/sport_config.py` (PRD-01) | Season start, week labels, 15-week table |
| `march_madness_backend/main.py` | `submit_pick` lock enforcement; `get_week_ranges`; leaderboard day lock queries |
| `march-madness-frontend/src/utils/etLockDay.js` | Rename/extend → shared lock-period utils; MM vs football |
| `march-madness-frontend/src/pages/Picks.jsx` | `SHOW_LOCK_OF_THE_DAY_UI`; copy; lock toggle week checks |
| `march-madness-frontend/src/pages/Live.jsx`, `Leaderboard.jsx`, `AdminUserPicks.jsx` | “day” → “week” when football |
| `march_madness_backend/tests/test_scoring.py` | Unit tests for bounds |

### Similar Implementations
- Backend football week math (historical):

```python
# Wed 00:00 → Tue 23:59 America/New_York (use ZoneInfo, not fixed UTC-5)
days_since_wednesday = (local.weekday() - 2) % 7
week_start = local.date() - timedelta(days=days_since_wednesday) at 00:00 ET
week_end = week_start + 7 days  # exclusive end at next Wed 00:00 is cleaner
```

Prefer **half-open interval** `[week_start, next_week_start)` in UTC for comparisons to avoid 11:59:59 bugs.

### Architecture Notes
- All lock-period comparisons must use **`America/New_York`** via `ZoneInfo` (DST-safe). Do **not** use fixed `UTC-5`.
- Frontend and backend must share the same week definition (tests + one documented table).
- When `SPORT_MODE=march_madness`, keep existing day-bound behavior unchanged.

### Database/API Context
No new collections. Picks still store `lock: bool`. Games still store `game_date`.

API additions / changes:
- `GET /leaderboard/weeks` — return Overall + 15 football weeks when mode is football (implementation can land here; PRD-03 wires leaderboard filter behavior fully).
- `submit_pick` — one lock per week when football.

---

## 3. Design Decisions (Pre-Made)

### Approach
**Season calendar (2026), Wed-start weeks:**

| Index | Week starts (Wed 00:00 ET) | Label |
|------:|---------------------------|--------|
| 0 | 2026-08-26 | CFB Week 0 |
| 1 | 2026-09-02 | CFB Week 1 |
| 2 | 2026-09-09 | CFB Week 2, NFL Week 1 |
| 3 | 2026-09-16 | CFB Week 3, NFL Week 2 |
| … | +7 days each | CFB Week `{i}`, NFL Week `{i-1}` for `i >= 2` |
| 14 | 2026-12-02 | CFB Week 14, NFL Week 13 |

- Season spans **15 weeks**, starting week of **8/29** (contained in Wed 8/26 week) through week of **12/4** (Wed 12/2 week).
- Filter keys: `overall`, `week_0` … `week_14`.
- **Auto-detect current week:** find index where `week_start <= now_et < week_start+7d`; if before week 0 → `week_0`; if after week 14 → `week_14` (or `overall` — **use last week** for picks context, `overall` only as explicit filter default on leaderboard is PRD-03: default filter = current week).

**Lock of the week:**
- Max **one** `lock=true` pick per user whose `game_date` falls in the same Wed–Tue week.
- Setting a new lock in that week unlocks the previous unlocked-eligible lock (same behavior as current same-day unlock, but week-scoped).
- Cannot change lock on a game once picks are locked for that game (`PICK_LOCK_BEFORE_TIP` = 1 minute).
- Scoring unchanged: correct lock → 2 points; correct non-lock → 1; push → 0.

**UI:**
- Set `SHOW_LOCK_OF_THE_DAY_UI = true` when football (or rename to `SHOW_LOCK_UI` and drive from `/app-config`).
- Copy: “lock of the week”, not “day”. Reminder: lock attaches to the **week the game is played**.

### Rationale
Matches prior football pool rules and owner’s 15-week CFB/NFL labeling. Half-open ET weeks avoid DST and 11:59 edge bugs that existed in older EST-fixed code.

### Patterns/Libraries
- `zoneinfo.ZoneInfo("America/New_York")` (already used in `scoring.py`).
- Mirror helpers in JS with the same civil-time approach as `etLockDay.js`.

### Code Organization
```
sport_config.py     → FOOTBALL_SEASON_START, week label table, filter keys
scoring.py          → get_lock_week_bounds(), same_lock_week(), get_lock_day_bounds() kept
etLockDay.js        → add getLockWeekBounds / sameLockWeek; keep day helpers for MM
main.py             → branch submit_pick on sport mode
```

---

## 4. Implementation Guidance

### Step-by-Step Plan
1. Encode the 15-week table in `sport_config.py` (do not derive labels ad hoc in the UI).
2. Implement `get_lock_week_bounds(dt_utc) -> (start_utc, end_utc_exclusive)` in `scoring.py`.
3. Implement `get_week_filter_for_datetime(dt) -> "week_N"` and `list_football_week_ranges()` for `/leaderboard/weeks`.
4. In `submit_pick`, when `SPORT_MODE=football`:
   - Replace `get_lock_day_bounds` checks with `get_lock_week_bounds`.
   - Error copy: mention “same week (Wed–Tue ET)”.
5. When `SPORT_MODE=march_madness`: keep existing day logic path.
6. Frontend: port week helpers; update Picks lock toggle to week scope; set show-lock flag true for football.
7. Update AdminUserPicks / Live / Leaderboard lock wording via `/app-config.lock_label`.
8. Expand unit tests for week boundaries around Wed midnight ET and DST (2026-11-01).

### Key Functions/Methods
```python
def get_lock_week_bounds(dt_utc) -> tuple[datetime, datetime]:
    """Return [Wed 00:00 ET, next Wed 00:00 ET) as UTC datetimes."""

def football_week_index(dt_utc) -> int:
    """0..14 clamped to season, based on sport_config start."""

def week_label(index: int) -> str:
    if index == 0: return "CFB Week 0"
    if index == 1: return "CFB Week 1"
    return f"CFB Week {index}, NFL Week {index - 1}"
```

### Data Flow
```
User toggles lock on game G
  → frontend ensures no other started locked game in same week (UX)
  → POST submit_pick { lock: true }
  → backend loads user's lock=true picks
  → for each other lock in same week: if other game still unlocked, set lock false; if other already tip-locked, 400
  → save pick
```

### Complex Logic Breakdown
**Same-week detection:** convert both `game_date`s to ET, compute week_start (Wed 00:00), compare week_start equality (or compare bounds overlap).

**Season membership:** games before 2026-08-26 00:00 ET or on/after 2026-12-09 00:00 ET are outside the 15-week table — still allow admin to create them, but filter key should clamp or show under nearest week; **prefer clamp into week_0 / week_14** and log warning.

### Code Examples
Port structure from current day lock block in `main.py` (~lines 769–795), swapping `get_lock_day_bounds` → `get_lock_week_bounds` and updating error strings.

---

## 5. Edge Cases and Error Handling

| Edge case | Behavior |
|-----------|----------|
| Two games same week, lock A then lock B | A unlocked if A’s picks still open; else 400 |
| Unlock after tip lock | 400 — same as today |
| Game Wednesday 12:00:00.000 ET | Starts **new** week |
| Game Tuesday 23:59 ET | Still previous week |
| DST fall back / spring forward | ZoneInfo handles; test both |
| MM mode | Day bounds unchanged |
| Lock UI hidden accidentally | Must be visible for football |

### Error Messages (football)
- `Cannot lock this game because you already have a lock on a game whose picks have locked for the same week (Wed–Tue ET).`
- `Cannot unlock — picks lock 1 minute before scheduled tip-off.`
- Keep existing tip-lock messages for pick edits.

### Validation
- `lock` boolean optional on submit (unchanged).
- Reject lock=true if game_id missing / game not found.

---

## 6. Likely Pitfalls to Avoid

- Using browser local TZ instead of ET for week math.
- Reintroducing fixed `UTC-5` from `football_pool`.
- Leaving `SHOW_LOCK_OF_THE_DAY_UI = false`.
- Filtering leaderboard with old `first_half` / `second_half` keys while locks use weeks (complete filter swap in PRD-03; this PRD must at least emit week keys from `/leaderboard/weeks`).
- Frontend week start using `getDay()` without ET conversion (historical football Picks bug risk).
- Treating “week of 8/29” as starting Wednesday 8/29 — **8/29/2026 is Saturday**; week starts **Wed 8/26**.

---

## 7. Testing Requirements

### Unit Tests (`tests/test_scoring.py`)
- Wed 2026-08-26 00:00 ET ∈ week 0 start
- Sat 2026-08-29 → week 0, label CFB Week 0
- Wed 2026-09-09 → week 2, label includes NFL Week 1
- Tue 2026-09-08 23:59 ET → still week 1
- Wed 2026-09-09 00:00 ET → week 2
- `same_lock_week` true/false pairs
- MM: `get_lock_day_bounds` still 3am-based

### Manual
- [ ] Lock game Thu, lock another Fri same week → only second locked
- [ ] After kickoff-1min, cannot move lock
- [ ] Picks page shows lock controls + week wording
- [ ] `/leaderboard/weeks` lists Overall + 15 labels in order

---

## 8. Acceptance Criteria

- [ ] Football mode: exactly one LOTW per Wed–Tue ET week
- [ ] Scoring still 1 / 2 / 0 with existing `score_pick_points`
- [ ] Picks still freeze 1 minute before tip
- [ ] 15-week table and labels match the table in this PRD
- [ ] Lock UI re-enabled for football
- [ ] March Madness lock-of-day code path still works when `SPORT_MODE=march_madness`
- [ ] Unit tests cover week boundaries + labels

---

## 9. Dependencies and Considerations

### External Services
None.

### Database
None.

### Configuration
Uses `SPORT_MODE` from PRD-01. Season start constant in `sport_config.py` (not env), unless you add `FOOTBALL_SEASON_YEAR=2026`.

### Breaking Changes
- Leaderboard filter keys change from `first_half`/`second_half` → `week_N` (PRD-03 must update consumers in same release train).

### Migration Steps
Ship with PRD-01 after DB wipe so no old day-lock picks exist.

---

## 10. Project Notes

### Important Notes
- Both NFL and CFB games share the **same** week bucket and **one** shared LOTW (not per-sport locks).
- Tiebreaker ranking rules are PRD-03; this PRD only ensures TB `start_time` can be mapped into a week via the same bounds.

### Assumptions
- 2026 calendar dates above are correct for “week of 8/29” … “week of 12/4”.
- Owner accepts CFB Week 14 / NFL Week 13 as final label for week index 14.

---

## 11. Attachments and References

- `origin/football_pool` Picks.jsx week helpers
- `afcf728` LOTW backend enforcement history
- No ticket attachments folder
