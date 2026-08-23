# PRD-03: Leaderboard Record + Tiebreakers, Live Scores, Admin Resolve

## 1. Problem Statement and Context

### What
For football mode: leaderboard **Overall + auto week filters**; sort by **pick scoring record (points)** with **one numerical admin tiebreaker** (closest guess wins) as the ranking tiebreak. Update Live/CBS sources to **NFL + CFB**. Games are **admin-resolved only** (no working cron). Align Stats, Admin user-picks, and related pages with week periods. Skip password work.

### Background
Today’s leaderboard sorts by `total_points`, then `correct_locks`, and uses TB diffs only on non-`overall` filters with March Madness halves. Owner wants week-based competition, record-first ranking, and a single numerical TB for ties. Auto-resolve never worked — keep Live scrape for **display**, admin sets `winning_team` manually.

### Related Work
- Depends on: [PRD-01](./PRD-01-football-foundation.md), [PRD-02](./PRD-02-lock-of-the-week-calendar.md)
- Current sort: `_leaderboard_list_for_filter` in `main.py`
- Live/CBS: `CBS_SCOREBOARD_URL` + `fetch` helpers near bottom of `main.py`
- Deprecated cron: PRD-01

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Role |
|------|------|
| `march_madness_backend/main.py` | `_leaderboard_list_for_filter`, `_filter_by_week`, Live endpoints, `update_game` / resolve, CBS scrape |
| `march_madness_backend/sport_config.py` | Week keys/labels |
| `march-madness-frontend/src/pages/Leaderboard.jsx` | Filter dropdown, points/locks display, TB diffs |
| `march-madness-frontend/src/pages/Stats.jsx` | Half/week stats |
| `march-madness-frontend/src/pages/Live.jsx` | Live scores matching |
| `march-madness-frontend/src/pages/AdminGames.jsx` | Manual winner / scores |
| `march-madness-frontend/src/pages/AdminTiebreakers.jsx` | Numerical TB question + answer |
| `march-madness-frontend/src/pages/AdminUserPicks.jsx` | Lock progress “current day” → week |
| `march-madness-frontend/src/pages/Picks.jsx` | Tiebreaker questions UX |
| `march-madness-frontend/src/utils/etLockDay.js` | `groupPicksByTournamentHalf` → week grouping |
| `docs/AUTO_RESOLVE.md` | Already deprecated in PRD-01 |

### Similar Implementations
- TB accuracy diff already computed in `_leaderboard_list_for_filter`.
- Admin `PUT /games/{id}` already triggers rescoring via `update_game_scores`.

### Architecture Notes
- Leaderboard cache (`_cache` / `leaderboard_v1`) must invalidate on game resolve and TB answer publish (existing invalidation paths — verify TB answer update clears cache).
- Live page may scrape CBS without writing winners.

### Database/API Context
**No schema change required.** Conventions:
- Tiebreaker `answer` must be numeric string when used for ranking (admin enters after games).
- Prefer **one numerical TB per week** (admin discipline); if multiple exist in a week, use **earliest `start_time`** as TB1 only (ignore 2nd/3rd for football sort).

Endpoints to verify/update:
- `GET /leaderboard?filter=overall|week_N`
- `GET /leaderboard/weeks`
- `GET /user_all_past_picks/{uid}?filter=...`
- `GET /stats` (week-aware)
- `GET /api/gamescores` or live score helper — scrape **both** football boards
- Admin game update (resolve) — unchanged contract

---

## 3. Design Decisions (Pre-Made)

### Approach

#### Ranking (“record”)
For football mode, define **record** as **total points from game picks only** using existing scoring (1 correct, 2 correct lock, 0 push).  

**Sort key (all filters including Overall):**
1. `total_points` descending (game picks only — **do not** add `tiebreaker_picks.points_awarded` into this total in football mode)
2. `first_tiebreaker_diff` ascending (closer better; missing TB → `999999`)
3. `correct_locks` descending (final fallback only)
4. `display_name` ascending (stable)

**Do not** use second/third TB diffs for football ranking.

#### Tiebreaker product rules
- Admin creates a **numerical** question (e.g. “Total points in SNF game”).
- Users submit numeric guesses before TB lock time (existing TB pick flow).
- Admin sets correct numeric `answer`.
- Ranking uses `abs(user_answer - correct)`; **closest wins the tie** (does not award pool points unless you already award them — **football mode: ranking only, points_awarded for TB stays 0 / ignore in totals**).

#### Filters
- Dropdown: **Overall** first, then `week_0` … `week_14` with labels from PRD-02.
- **Default selected filter:** auto-detected **current** football week (PRD-02), not Overall.
- `_filter_by_week`: for `week_N`, include picks/games/TBs whose timestamp falls in that week’s bounds; `overall` = no date filter.

#### Live scores
- Scrape:
  - `https://www.cbssports.com/college-football/scoreboard/?layout=compact`
  - `https://www.cbssports.com/nfl/scoreboard/?layout=compact`
- Merge results for Live matching (reuse fuzzy name helpers).
- When `SPORT_MODE=march_madness`, keep college-basketball URL.
- **No** auto-write of `winning_team` from scrape this season.
- **No** “Sync scores” admin button this PRD (explicit later enhancement).

#### Admin resolve
- Admin uses Admin Games to set scores / covering team / PUSH (existing UI).
- Document in Admin UI helper text: “Auto-resolve is disabled; set results manually.”

#### Stats / Admin user-picks / modals
- Replace tournament-half grouping with football week grouping when mode is football.
- “Users with lock of the day” → “lock of the week” for current week window.
- Include these pages in scope (no password/forgot-password work).

### Rationale
Owner asked to sort by record with a numerical TB as first tiebreak. Points already encode lock weighting; excluding TB points from totals avoids double-using TB as both points and sort key. Dual CBS boards match prior football season. Admin-only resolve matches “cron never worked.”

### Patterns/Libraries
- Existing BeautifulSoup scrape loop; extend to URL list (as in `de5493a`).
- Existing leaderboard cache build lock.

### Code Organization
- Keep sort policy in `_leaderboard_list_for_filter` branched on `get_sport_mode()`.
- CBS URLs from `sport_config.py` (`scoreboard_urls()`).

---

## 4. Implementation Guidance

### Step-by-Step Plan
1. Replace `get_week_ranges` / `_filter_by_week` March Madness halves with football week bounds when mode is football; keep MM branch.
2. Rewrite football sort in `_leaderboard_list_for_filter` per decisions above; stop adding TB points into `total_points` for football.
3. Update `GET /leaderboard/weeks` payload; frontend Leaderboard drops hardcoded `first_half` fallbacks and uses API list; default filter = current week key from API (`current_week` field).
4. Stats: map best/worst week using football week table; remove hard-coded Mar 2026 half stats when football.
5. Live + `/api/gamescores`: multi-URL football scrape; MM single URL.
6. AdminUserPicks + Live lock indicators: current **week** bounds.
7. AdminGames: short note that resolve is manual.
8. Ensure finishing a TB (setting `answer`) invalidates leaderboard cache.
9. Manual QA with 2–3 users, one week of games, one numerical TB.

### Key Functions/Methods
```python
def scoreboard_urls() -> list[str]:
    if get_sport_mode() == "football":
        return [CFB_URL, NFL_URL]
    return [CBB_URL]

# filter
def _filter_by_week(items, date_key, filter_key):
    if filter_key == "overall": return items
    start, end = bounds_for_filter_key(filter_key)  # from sport_config
    ...
```

### Data Flow
```
Admin creates games + weekly numerical TB
Users submit picks + TB guess + LOTW
Admin sets game winning_team → rescore picks → invalidate cache
Admin sets TB answer → invalidate cache
GET /leaderboard?filter=week_2 → points sort → TB diff tiebreak
Live page → scrape CFB+NFL → match names → display only
```

### Complex Logic Breakdown
**Overall + TB:** For Overall, `first_tiebreaker_diff` = diff against the **earliest season TB that has a numeric answer**; if none answered yet, all diffs `999999` (pure points race).

**Week filter + TB:** Only TBs with `start_time` in that week count; take earliest as TB1.

**Pushes:** `points_awarded = 0`; they neither help nor hurt points (record is points-based, not W–L display required — optional UI: show `correct_picks` count next to points).

### Code Examples
Change football sort roughly to:
```python
leaderboard.sort(key=lambda x: (
    -x["total_points"],
    x["first_tiebreaker_diff"],
    -x["correct_locks"],
    x["display_name"],
))
```
Apply for **both** `overall` and `week_N` in football mode.

---

## 5. Edge Cases and Error Handling

| Case | Behavior |
|------|----------|
| No TB answer yet | All diffs 999999; order by points only |
| Non-numeric TB answer | Treat as unusable (999999); log warning |
| User skipped TB | 999999 (loses ties to anyone who entered) |
| Equal points + equal TB diff | `correct_locks` then name |
| CBS scrape fails | Live shows empty/partial; admin still resolves |
| Team name mismatch on Live | Existing fuzzy match; admin resolve unaffected |
| MM mode | Preserve old half filters + old sort (points, locks, 3 TB diffs on non-overall) |

### Validation
- Admin TB answer: prefer validating numeric on finish endpoint when `SPORT_MODE=football`.

### Error Messages
- If admin finishes TB with non-numeric answer in football mode: `400 Tiebreaker answer must be numeric for football ranking.`

---

## 6. Likely Pitfalls to Avoid

- Leaving Leaderboard.jsx hardcoded `first_half` / Mar 23 labels.
- Sorting Overall without TB while weeks use TB — football uses TB on Overall too (earliest answered).
- Re-enabling auto-resolve “just to try.”
- Scraping only NFL or only CFB.
- Counting TB `points_awarded` in football totals (double-counting vs ranking TB).
- Cache not invalidated when TB answer set → stale ranks.
- `groupPicksByTournamentHalf` still used in football user-picks modal.

---

## 7. Testing Requirements

### Unit
- `_filter_by_week` for `week_0`, `week_2`, `overall`
- Sort order: higher points win; equal points → lower TB diff wins; missing TB loses tie
- `scoreboard_urls()` mode switch

### Integration / manual
- [ ] Create 2 users, 3 games (mix CFB/NFL names), resolve with cover/push/lock
- [ ] Leaderboard week filter matches only that week’s games
- [ ] Default filter is current week
- [ ] Equal points broken by numerical TB
- [ ] Overall cumulative points + earliest TB
- [ ] Live shows games from both boards when available
- [ ] Admin resolve updates points without cron
- [ ] Stats page week labels sensible
- [ ] AdminUserPicks current-week lock list
- [ ] MM mode smoke: halves + basketball URL still work

### Test Data
- Sample spreads with `spread` >0 / <0 / 0
- TB question with answer `47.5`

---

## 8. Acceptance Criteria

- [ ] Football leaderboard filters: Overall + 15 weeks; default = current week
- [ ] Sort: game points desc, then numerical TB closeness asc (Overall + weekly)
- [ ] TB does not add to displayed `total_points` in football mode
- [ ] Live/CBS uses CFB + NFL boards in football mode
- [ ] Admin-only resolve path documented in UI; cron not required
- [ ] Stats, Admin user-picks, user picks modal week-aware in football mode
- [ ] Password/forgot-password **not** modified
- [ ] March Madness behavior preserved behind `SPORT_MODE=march_madness`

---

## 9. Dependencies and Considerations

### External Services
- CBS Sports HTML scoreboards (Live display only; brittle — expect occasional breakage).

### Database
- None beyond wiped empty season (PRD-01).

### Configuration
- `SPORT_MODE`, week table from PRD-02.

### Breaking Changes
- Filter query param values change; old bookmarked `?filter=first_half` ignored → treat as overall or 400 → **map unknown filters to `overall`**.

### Migration Steps
Deploy PRD-01→02→03 together or in order before inviting users. Create Week 0 games + TB after wipe.

---

## 10. Project Notes

### Important Notes
- Sync-scores button explicitly **out of scope** (later).
- One shared LOTW across NFL+CFB (PRD-02); leaderboard does not split sports.
- “Record” means **points record** from ATS picks, not a separate W–L sort order.

### Assumptions
- Admins will enter roughly one numerical TB per week.
- Closest absolute difference is fair even for decimal answers.
- 2026 season dates from PRD-02 are authoritative.

---

## 11. Attachments and References

- Commit `de5493a` dual football scoreboard scrape
- Leaderboard sort reference: `_leaderboard_list_for_filter` in `main.py`
- No `./attachments/` folder
