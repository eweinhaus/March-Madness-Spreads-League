# PRD-12: Football Leaderboard Sort — Wins, Then Locks

## 1. Problem Statement and Context

### What
Change **football-mode** leaderboard ranking so ties break by **total wins** (correct game picks), then **correct locks**. Stop using total points and numerical TB as football sort keys.

Display of points / W–L / locks on the board can stay; only the **sort order** changes.

### Background
Week 1 complaint: Blair Summers **7–1 / 7 pts / lock miss** ranked **behind** Kyle McGreevy **6–2 / 7 pts / lock hit**. Current football sort (PRD-03) is:

1. `total_points` DESC (game picks only; lock hit awards 2 pts)
2. `first_tiebreaker_diff` ASC
3. `correct_locks` DESC
4. `display_name` ASC

TB unset → both `999999` → Kyle's correct lock broke the 7–7 points tie. Product owner now wants **wins ahead of locks**, matching "better record should beat worse record with a lock."

Owner decision (2026-09-06 Spread Pools Chat):

1. **Total wins**
2. **Number of locks correct**

### Related Work
- [PRD-03](./PRD-03-leaderboard-live-football.md) — previous football sort (points → TB → locks); this PRD **supersedes** the football ranking section only
- `_leaderboard_list_for_filter` in `march_madness_backend/main.py`
- Leaderboard cache `_cache/leaderboard_v1` — must rebuild after deploy
- March Madness sort path — **unchanged**

### Out of scope
- Changing scoring (1 pt correct, 2 pt correct lock, 0 push)
- Changing displayed columns (points can remain visible)
- Auto-resolve / Live scrape
- Stats page ranking (unless it reuses the same football sort helper — then keep one shared policy)
- Season wipe

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Why |
|------|-----|
| `march_madness_backend/main.py` | `_leaderboard_list_for_filter` football branch sort key + row fields |
| `march_madness_backend/tests/` | Leaderboard sort tests (add/adjust football cases) |
| `march-madness-frontend/src/pages/Leaderboard.jsx` | Confirm it trusts API order; no client re-sort that reintroduces points-first |
| `docs/PRDs/PRD-03-leaderboard-live-football.md` | Historical; do not rewrite whole file — this PRD is the new source of truth for football sort |

### Similar Implementations
- Football vs March Madness already branches in `_leaderboard_list_for_filter`.
- `correct_locks` already counted when `points_awarded == 2` on a lock pick.
- `user_game_points` already summed from game picks only.

### Architecture Notes
- Sort runs when building the cached leaderboard. After code ships, invalidate leaderboard cache (existing invalidate helpers / next cold build).
- Do not hardcode Blair/Kyle names.

### Database/API Context
Add (or compute) per-row for football:

```text
correct_picks  # "wins": settled game picks with points_awarded > 0
```

Keep existing `total_points`, `correct_locks`, TB fields in the payload for display if the UI uses them. Ranking must not depend on `total_points` or TB diffs in football mode.

---

## 3. Design Decisions (Pre-Made)

### Approach

**Football sort key (all filters including Overall and `week_N`):**

1. `correct_picks` (**wins**) DESC  
   Definition: count of **settled** game picks for that user/period where `points_awarded > 0`.  
   - Push (`winning_team == "PUSH"` / 0 pts) does **not** count as a win.  
   - Incorrect settled picks do not count.  
   - Unsettled picks do not count.  
   - A correct lock counts as **one** win (and separately increments `correct_locks`).
2. `correct_locks` DESC
3. `display_name` ASC (case-insensitive) as final stable tiebreak

**Remove from football ranking:**
- `total_points` as a sort key
- `first_tiebreaker_diff` (and any TB) as a sort key

**Keep:**
- March Madness ranking logic unchanged
- Points still computed and returned for display
- Numerical TB product can still exist for future use / display; it just does not break football ties anymore

### Rationale
- Owner wants record (W–L wins) ahead of lock success when comparing players.
- Points encode lock bonus (2 vs 1), which caused Kyle (6 wins) to tie Blair (7 wins) on points and then win on locks — the complained behavior.
- Two-key sort matches the explicit chat order; name only for determinism.

### Patterns/Libraries
- Existing `_leaderboard_list_for_filter` + cache

### Code Organization
- Change only the football branch sort + ensure `correct_picks` is populated on each football row.
- Prefer computing `correct_picks` in the same loop that already tallies game points / locks.

---

## 4. Implementation Guidance

### Step-by-step Plan
1. In football path of `_leaderboard_list_for_filter`, count `correct_picks` per uid (settled, `points_awarded > 0`).
2. Include `correct_picks` on each leaderboard row.
3. Sort: `-correct_picks`, `-correct_locks`, `display_name.lower()`.
4. Update/add unit tests: Blair-shaped 7 wins 0 locks vs Kyle-shaped 6 wins 1 lock → Blair first when points would have tied.
5. Invalidate leaderboard cache on deploy / after merge.
6. Confirm frontend does not re-sort by points.

### Key Functions/Methods
- `_leaderboard_list_for_filter`
- Cache rebuild / `invalidate_leaderboard_cache`

### Data Flow
Unchanged fetch of picks/games → compute points, wins, locks → sort by wins then locks → cache → `GET /leaderboard`.

### Complex Logic Breakdown
**Win vs points:**  
Blair: 7 correct non-lock picks → 7 wins, 7 points, 0 correct locks.  
Kyle: 5 correct non-lock + 1 correct lock → 6 wins, 7 points, 1 correct lock.  
New sort: Blair (7 wins) above Kyle (6 wins).

**Period filters:** wins/locks counted only on picks included in that filter's game set (same as today's points scope).

### Code Examples

```python
# Football row (concept)
"correct_picks": user_correct_picks.get(uid, 0),
"total_points": user_game_points.get(uid, 0),  # display only
"correct_locks": user_correct_locks.get(uid, 0),

leaderboard.sort(key=lambda x: (
    -x["correct_picks"],
    -x["correct_locks"],
    x["display_name"].lower(),
))
```

---

## 5. Edge Cases and Error Handling

### Edge Cases
- Equal wins and equal correct locks → alphabetical `display_name`.
- All pushes / no settled picks → 0 wins; locks 0; name order.
- Correct lock: +1 win and +1 correct_locks.
- Hidden users (PRD-10) still excluded via `user_is_listed`.

### Error Scenarios
- None new; malformed picks already skipped in existing loops.

### Validation Requirements
- `correct_picks` never counts unsettled games.

### Error Messages
- N/A

---

## 6. Likely Pitfalls to Avoid

### Common Mistakes
- Sorting by `total_points` first "and also" wins — owner wants wins first, not points.
- Counting a correct lock as two wins.
- Leaving TB diff in the football sort key.
- Changing March Madness sort accidentally.
- Frontend re-sorting by points after fetch.

### Gotchas
- Stale leaderboard cache will keep old order until invalidated.
- Stats page may show different ordering if separate — only required to fix leaderboard unless shared helper.

### Performance Concerns
- One extra integer tally per user; negligible.

### Security Considerations
- None.

### Integration Issues
- Document for operators: numerical TB no longer breaks weekly football ties.

---

## 7. Testing Requirements

### Test Scenarios
1. 7 wins / 0 locks vs 6 wins / 1 lock, same points → 7-win user ranks higher.
2. Equal wins, 1 correct lock vs 0 → lock user ranks higher.
3. Equal wins and locks → name ASC.
4. March Madness path still uses prior multi-TB / points behavior.
5. Week filter and Overall both use the new football key.

### Unit Tests
- Table-driven tests around `_leaderboard_list_for_filter` football branch (mock users/picks/games).

### Manual Testing
- Live Week 1: Blair above Kyle after cache refresh.

### Test Data
- Synthetic uids; optional prod smoke after deploy.

---

## 8. Acceptance Criteria

### Functional Requirements
- [ ] Football leaderboard sort is wins DESC → correct locks DESC → name ASC.
- [ ] Football sort does **not** use `total_points` or TB diffs.
- [ ] Points still available on API/UI for display.
- [ ] March Madness ranking unchanged.
- [ ] Week 1 style case: more wins ranks above fewer wins even if fewer correct locks / equal points.
- [ ] Leaderboard cache reflects new order after deploy.

### User-Facing Behavior
- Better W–L (more wins) ranks above a worse record that hit LOTW when comparing weekly/overall football standings.

### Performance Requirements
- No new indexes.

### Security Requirements
- N/A

---

## 9. Dependencies and Considerations

### External Services
- None new.

### Database Changes
- None (computed field only).

### Configuration
- None.

### Breaking Changes
- Anyone relying on points-first or TB-first football ties will see new order (intentional).

### Migration Steps
1. Merge + deploy API.
2. Invalidate leaderboard cache if deploy doesn't cold-miss quickly.
3. QA Week filter Blair vs Kyle.

---

## 10. Project Notes from Ticket

### Important Notes
- Product call from Ethan Weinhaus in Spread Pools Chat after Week 1 Blair vs Kyle report.
- Execute may ship code in parallel; this PRD is the durable spec and supersedes PRD-03 football **ranking** bullets.
- Owner listed exactly two keys (wins, correct locks); name is implementation tiebreak only.

### Assumptions
- "Total wins" = correct settled picks (`points_awarded > 0`), aligning with displayed W–L wins.
- TB drops out of football ranking entirely unless owner later reinstates it.

---

## 11. Attachments and References

- `docs/PRDs/PRD-12-football-sort-wins-then-locks.md`
- `docs/PRDs/PRD-03-leaderboard-live-football.md` (old sort)
- Spread Pools Chat 2026-09-06 Week 1 standings thread
