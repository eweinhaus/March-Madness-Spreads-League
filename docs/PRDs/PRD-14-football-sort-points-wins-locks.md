# PRD-14: Football Leaderboard Sort — Points, Then Wins, Then Locks

## 1. Problem Statement and Context

### What
Change the **football-mode** leaderboard ranking to:

1. `total_points` DESC
2. `total_wins` DESC
3. `correct_locks` DESC
4. `display_name` ASC (case-insensitive; same name fallback as today)

This **replaces** PRD-12 / `football_wins_locks_name_v1` (wins → locks → name).

This is **not** a full revert to PRD-03. Old PRD-03 football sort was points → numerical TB diff → locks. The new order uses **wins** as the first tiebreaker and keeps **numerical TB out of the sort** (TB remains display/scoring-adjacent only for football — scoring rules unchanged).

### Background
PRD-12 shipped as impl PR #41: sort by ATS wins then correct locks; points stayed on the row but did not decide rank. League commissioner now wants points to decide rank again, with wins as first tiebreaker, then locks. Ethan confirmed ship (2026-09-14).

Current code (`_leaderboard_list_for_filter`, football branch):

```python
leaderboard.sort(key=lambda x: (
    -x["total_wins"],
    -x["correct_locks"],
    x["display_name"].lower(),
))
LEADERBOARD_SORT_VERSION = "football_wins_locks_name_v1"
```

### Related Work
- [PRD-03](./PRD-03-leaderboard-live-football.md) — original football leaderboard (points → TB → locks)
- [PRD-12](./PRD-12-football-sort-wins-then-locks.md) — wins → locks → name (current live)
- `march_madness_backend/main.py` — `_leaderboard_list_for_filter`, `LEADERBOARD_SORT_VERSION`, cache rebuild
- Frontend leaderboard badges (wins badge on; TB badge gated off for football per PRD-12 — keep unless product asks otherwise)

### Out of scope
- Changing how `total_points` or `total_wins` are **scored** (game-pick points only in football; TB still not added into football points)
- Putting numerical TB back into the football sort key
- March Madness mode sort
- Stats-page sort (separate from leaderboard unless it reuses the same helper — if it does, match football leaderboard; if not, leave stats alone)
- Live page ranking UI beyond whatever already mirrors leaderboard order

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Why |
|------|-----|
| `march_madness_backend/main.py` | Football sort key + `LEADERBOARD_SORT_VERSION` |
| Leaderboard cache build / invalidate | Stale ranks must not survive after version bump |
| Frontend leaderboard (if any client-side re-sort) | Must trust API order or match new key |
| Tests for football leaderboard sort | Update expectations from PRD-12 |

### Similar Implementations
- PRD-12 already returns `total_points`, `total_wins`, `correct_locks` on each row — only the `sort` key and version string change.
- Cache: bump `LEADERBOARD_SORT_VERSION` so old cached boards are not served.

### Architecture Notes
- Apply the new key for **all** football leaderboard filters (overall and week filters), same as PRD-12.
- Prefer a new version id, e.g. `football_points_wins_locks_name_v1`.

### Database/API Context
No schema change. Response fields stay; rank order changes.

---

## 3. Design Decisions (Pre-Made)

### Approach
Replace football sort with:

```python
leaderboard.sort(key=lambda x: (
    -x["total_points"],           # Points DESC
    -x["total_wins"],             # ATS wins DESC (first tiebreaker)
    -x["correct_locks"],          # Correct locks DESC
    x["display_name"].lower(),    # Name ASC
))
LEADERBOARD_SORT_VERSION = "football_points_wins_locks_name_v1"
```

Update comments near the football branch to match.

### Rationale
- Points primary restores commissioner preference after PRD-12.
- Wins before locks gives a meaningful first tiebreaker without bringing TB diffs back into ranking.
- Name fallback unchanged for total ties.

### Patterns/Libraries
- Existing `_leaderboard_list_for_filter` + cache version pattern.

### Code Organization
- One-line sort change + version bump + tests + comment sync. Docs PRD-14 in `docs/PRDs/`.

---

## 4. Implementation Guidance

### Step-by-step Plan
1. Change football `leaderboard.sort` key as above.
2. Bump `LEADERBOARD_SORT_VERSION` to `football_points_wins_locks_name_v1` (or equivalent clear name).
3. Update unit tests that assert wins-first order to points→wins→locks→name.
4. Confirm week filters use the same sort (no special-case overall).
5. Deploy API; ensure cache rebuild / version miss so prod ranks refresh.
6. Smoke: pick two adjacent players where points diverge from wins (e.g. higher points but fewer wins should rank above).

### Key Functions/Methods
- `_leaderboard_list_for_filter` (football branch)
- `LEADERBOARD_SORT_VERSION`
- Cache read path that checks sort version

### Data Flow
Unchanged: build rows → sort → cache → API → UI.

### Complex Logic Breakdown
**Wins vs points example:** Player A 18 pts / 15 wins ranks above Player B 16 pts / 16 wins because points are primary.

**Equal points:** Higher `total_wins` ranks first; if still tied, higher `correct_locks`; if still tied, name ASC.

### Code Examples
See Approach.

---

## 5. Edge Cases and Error Handling

### Edge Cases
- Equal points, wins, and locks → alphabetical by display_name (case-insensitive).
- Zero points / zero wins / zero locks → still sorted; empty board unchanged.
- Hidden users (PRD-10/13) remain excluded from the list before sort.
- `first_tiebreaker_diff` may still be computed/returned for football rows — **do not** put it back in the sort key.

### Error Scenarios
- Stale cache without version bump → wrong ranks; version bump is mandatory.

### Validation Requirements
- Football scoring still: `total_points` = game picks only (no TB points added).

### Error Messages
- None user-facing for this change.

---

## 6. Likely Pitfalls to Avoid

### Common Mistakes
- Reintroducing `first_tiebreaker_diff` into the football sort (that would be PRD-03, not this PRD).
- Sorting only "overall" and leaving week filters on wins-first.
- Forgetting to bump `LEADERBOARD_SORT_VERSION`.
- Client-side re-sort by wins that overrides API order.
- Changing MM mode sort.

### Gotchas
- Frontend may still show a wins badge; that is fine. Rank must follow the new key.
- Docs PRD-12 remains historical; PRD-14 supersedes it for football ranking.

### Performance Concerns
- None (same O(n log n) sort).

### Security Considerations
- None.

### Integration Issues
- QA should re-check Brian/Hunter-style pairs where points and wins disagree.

---

## 7. Testing Requirements

### Test Scenarios
1. A (20 pts, 10 wins, 0 locks) ranks above B (18 pts, 12 wins, 2 locks).
2. Equal points: higher wins ranks first.
3. Equal points and wins: higher correct_locks ranks first.
4. Full tie: name ASC (`alice` before `bob`).
5. Week filter and overall both use the new key.
6. After deploy, cache serves new order (version bump).

### Unit Tests
- Update / add sort-key tests covering the four-level key.

### Manual Testing
- Live leaderboard: confirm a points-led ranking where a lower-win player with more points is above a higher-win player with fewer points.

### Test Data
- Synthetic rows in unit tests; prod smoke on current week board.

---

## 8. Acceptance Criteria

### Functional Requirements
- [ ] Football leaderboard ranks by points DESC, then wins DESC, then correct locks DESC, then name ASC.
- [ ] Numerical TB diff is **not** in the football sort key.
- [ ] Scoring unchanged (football points still game picks only).
- [ ] `LEADERBOARD_SORT_VERSION` bumped; stale wins-first cache not served.
- [ ] All football leaderboard filters use the new sort.
- [ ] March Madness sort unchanged.

### User-Facing Behavior
- Points decide who is #1 when points differ; wins/locks only break ties.

### Performance Requirements
- No new indexes or endpoints.

### Security Requirements
- None new.

---

## 9. Dependencies and Considerations

### External Services
- None.

### Database Changes
- Cache doc content regenerates; no user-doc migration.

### Configuration
- Sort version constant only.

### Breaking Changes
- Rank order changes vs PRD-12 for some pairs (intentional).

### Migration Steps
1. Merge impl PR + deploy API.
2. Confirm cache rebuild / version miss.
3. QA smoke on leaderboard.

---

## 10. Project Notes from Ticket

### Important Notes
- Product: Ethan via Orchestrator, 2026-09-14.
- Locked: points → wins → locks → name; not full PRD-03 revert; TB not in sort.
- Context: commissioner preference after Brian/Hunter "wins vs points" confusion on the board.

### Assumptions
- `total_wins` is the same ATS wins field already on leaderboard rows from PRD-12.
- Repo: `eweinhaus/March-Madness-Spreads-League`.

---

## 11. Attachments and References

- `docs/PRDs/PRD-14-football-sort-points-wins-locks.md`
- `docs/PRDs/PRD-12-football-sort-wins-then-locks.md` (superseded for sort order)
- `docs/PRDs/PRD-03-leaderboard-live-football.md` (historical; TB-in-sort not restored)
- Impl note: prior wins-first was GitHub PR #41
