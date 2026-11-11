# PRD-15: Football Leaderboard Sort Split by Filter (Weekly Uses Tiebreaker)

## 1. Problem Statement and Context

### What
Split the **football-mode** leaderboard sort by filter:

- **Weekly views** (`week_N` filters, i.e. any football filter other than `overall`):
  1. `total_points` DESC
  2. `total_wins` DESC
  3. `first_tiebreaker_diff` ASC (closest tiebreaker guess ranks higher)
  4. `display_name` ASC (case-insensitive)
- **Overall / full season** (`overall`): unchanged from PRD-14: `total_points` DESC, `total_wins` DESC, `correct_locks` DESC, `display_name` ASC.
- **March Madness mode:** untouched.

Missing or non-numeric tiebreaker guesses already compute as `first_tiebreaker_diff = 999999`, so they rank last among otherwise-tied players. Correct locks are **not** a weekly sort key.

### Background
PRD-14 (impl PR #45) made all football filters use points, wins, locks, name. Numerical TB was computed but not ranked. Ethan and the league commissioner approved (2026-11-10) using tiebreaker closeness to break ties on weekly boards, while keeping the season board as-is.

Trigger case, Week 10: four players tie at 9 points / 8 wins / 1 correct lock. TB actual = 29; guesses 41, 44, 45, 48. Under PRD-14 they fall back to name order; under PRD-15 they rank by closeness.

### Related Work
- [PRD-03](./PRD-03-leaderboard-live-football.md): original football board (points, TB, locks)
- PRD-12 (wins, locks; superseded)
- PRD-14 (points, wins, locks, name; stays for overall)
- `march_madness_backend/main.py` `_leaderboard_list_for_filter`

### Out of scope
- Scoring changes (football points still game picks only; TB awards no points)
- March Madness sort
- Stats page sort
- Using second/third tiebreakers in football

---

## 2. Technical Context

### Relevant Files/Modules
| Path | Why |
|------|-----|
| `march_madness_backend/main.py` ~573 | `LEADERBOARD_SORT_VERSION`, must bump |
| `march_madness_backend/main.py` ~663-667 | Docstring describing football sort |
| `march_madness_backend/main.py` ~693-714, ~727 | `first_tiebreaker_diff` computation (earliest TB in the filtered window; 999999 when missing/non-numeric/unanswered) |
| `march_madness_backend/main.py` ~740-746 | Football sort (`# Same sort for all filters`) |
| `march-madness-frontend/.../Leaderboard.jsx` ~167 | Comment says TB is not part of ranking; update to say it breaks weekly ties |
| `tests/test_leaderboard_ranking.py` | Add weekly vs overall cases |

### Architecture Notes
- `filter_key` is already passed into `_leaderboard_list_for_filter`. Branch on `filter_key == "overall"` inside the football block (mirrors the March Madness branch that already does this).
- The week filter already scopes `filtered_tb_picks` to that week, so `first_tiebreaker_diff` on a week board reflects that week's tiebreaker.
- If a tiebreaker has no answer yet, it is skipped, so every player gets 999999 and the TB key is a no-op (falls through to name). That is intended.

### Database/API Context
No schema change. Response fields unchanged; only rank order on weekly filters changes.

---

## 3. Design Decisions (Pre-Made)

### Approach
```python
if filter_key == "overall":
    leaderboard.sort(key=lambda x: (
        -x["total_points"],
        -x["total_wins"],
        -x["correct_locks"],
        x["display_name"].lower(),
    ))
else:  # week_N
    leaderboard.sort(key=lambda x: (
        -x["total_points"],
        -x["total_wins"],
        x["first_tiebreaker_diff"],   # smaller gap ranks higher; 999999 last
        x["display_name"].lower(),
    ))

LEADERBOARD_SORT_VERSION = "football_week_tb_overall_locks_v1"
```
Update the docstring and comments to describe both branches.

### Rationale
Weekly boards get a real tiebreaker (the reason weekly TB questions exist). The season board keeps locks as its tiebreaker so it stays stable.

### Code Organization
Sort change, version bump, docstring/comment updates, tests. No new modules.

---

## 4. Implementation Guidance

### Step-by-step Plan
1. Replace the single football sort with the overall/weekly branch above.
2. Bump `LEADERBOARD_SORT_VERSION` so cached boards rebuild.
3. Update docstring (~663-667) and the `Same sort for all filters` comment.
4. Update `Leaderboard.jsx` comment (~167). If the UI shows a TB badge/column gated off for football, leave display behavior as-is unless trivial; ranking comes from the API.
5. Add tests (section 7).
6. Deploy API; confirm cache version miss rebuilds.

### Key Functions/Methods
- `_leaderboard_list_for_filter` (football branch)
- `LEADERBOARD_SORT_VERSION`

### Complex Logic Breakdown
Example Week 10, all at 9 pts / 8 wins / 1 lock, TB actual 29:

| Player | Guess | Diff | Rank |
|--------|-------|------|------|
| Bryce Unruh | 41 | 12 | 1 |
| Kyle McGreevy | 44 | 15 | 2 |
| Brett Bell | 45 | 16 | 3 |
| zack ledesma | 48 | 19 | 4 |

---

## 5. Edge Cases and Error Handling

- No TB guess, or non-numeric guess: diff 999999, ranks below tied players with valid guesses.
- TB not yet answered: all 999999, falls to name.
- Equal diffs (e.g. guesses 25 and 33 with actual 29): falls to name ASC.
- Multiple TBs in a week: keep existing behavior (earliest TB by `start_time` is `first_tiebreaker_diff`).
- Hidden users (PRD-10/13) still excluded before sorting.

---

## 6. Likely Pitfalls to Avoid

- Changing the overall sort (must stay PRD-14).
- Putting correct locks into the weekly key.
- Sorting TB diff DESC (must be ASC: smaller gap wins).
- Forgetting the version bump (stale cached ranks).
- Touching March Madness sort.

---

## 7. Testing Requirements

Add to `tests/test_leaderboard_ranking.py`:
1. Week filter: equal points and wins, different diffs: smaller diff ranks first.
2. Week filter: higher points still beats better TB.
3. Week filter: equal points, higher wins beats better TB.
4. Week filter: missing guess (999999) ranks below a valid guess when otherwise tied.
5. Week filter: equal diffs fall to name ASC.
6. Week filter: correct locks do not affect order (player with more locks but worse TB ranks lower when points/wins tie).
7. Overall filter: unchanged PRD-14 order (locks break ties, TB ignored).
8. Week 10 fixture reproducing the table in section 4.

### Manual / prod acceptance
- `week_10` shows Bryce Unruh, Kyle McGreevy, Brett Bell, zack ledesma in that order.
- `week_1` order unchanged (Kyle above Reid).
- `overall` order unchanged vs before deploy.

---

## 8. Acceptance Criteria

- [ ] Football weekly filters sort points DESC, wins DESC, first_tiebreaker_diff ASC, name ASC.
- [ ] Football overall sort unchanged (points, wins, correct locks, name).
- [ ] Missing/non-numeric TB = 999999, ranked last among ties.
- [ ] March Madness sort unchanged.
- [ ] `LEADERBOARD_SORT_VERSION` bumped; cached boards rebuild.
- [ ] Docstring and Leaderboard.jsx comment updated.
- [ ] New tests pass; week_10 / week_1 / overall prod checks pass.

---

## 9. Dependencies and Considerations

- No external services or schema changes.
- Breaking change: weekly rank order changes for TB-separated ties (intended).
- Migration: merge, deploy, confirm cache rebuild, QA the three checks above.

---

## 10. Project Notes from Ticket

- Approved by Ethan and the league commissioner via Orchestrator, 2026-11-10. No interview needed.
- Code pointers from prod commit `ff32a4c`.
- Supersedes PRD-14 for weekly filters only; PRD-14 remains the overall sort.

---

## 11. Attachments and References

- `docs/PRDs/PRD-15-weekly-football-sort-tiebreaker.md`
- PRD-14 (docs PR #44, impl PR #45)
- `march_madness_backend/main.py`, `tests/test_leaderboard_ranking.py`
