# Virginia @ Louisville Missing from Live Page - Diagnosis

## Current Status

### ✅ CBS Sports (Confirmed)
The game IS live on CBS Sports:
- **Away Team**: `'Virginia'`
- **Home Team**: `'Louisville'`
- **Score**: Virginia 7 - Louisville 7
- **Status**: 2nd Quarter, 7:42 remaining
- **CBS Game #**: 16 out of 51 games

### ❓ Your Application
The game is **NOT showing** on the `/live` page.

## Root Cause Analysis

The `/live_games` endpoint (backend `main.py` lines 1794-1826) returns games based on these criteria:

```python
WHERE g.game_date <= current_time     # Game has started
AND (g.winning_team IS NULL OR g.winning_team = '')  # No winner yet
```

### Possible Reasons Why Virginia @ Louisville Is Not Showing

#### 1. ❌ Game Not in Database
**Most Likely**: The Virginia @ Louisville game was never added to the database.

**How to verify:**
- Check the Admin Games page
- Look for Virginia @ Louisville (or any variation like "UVA @ Louisville")

**Solution**: Add the game to the database via Admin panel

#### 2. ⏰ Game Date is in the Future
The game's `game_date` field in the database might be set to a future time, so the backend thinks it hasn't started yet.

**How to verify:**
- Check the game's date in the Admin Games page
- Current time (UTC): 2025-10-04 (game is live NOW)

**Solution**: Update the game date to the correct start time

#### 3. 🏁 Game Marked as Complete
The `winning_team` field might have been set accidentally, marking the game as finished.

**How to verify:**
- Check if the game has a winner set in the Admin Games page

**Solution**: Clear the `winning_team` field (set to NULL)

#### 4. 🔤 Team Name Mismatch in Database
The database might have:
- "UVA" instead of "Virginia"
- "Louisville Cardinals" instead of "Louisville"
- Different spellings or abbreviations

**How to verify:**
- Search the Admin Games page for:
  - "Virginia", "UVA", "Cavaliers"
  - "Louisville", "Cardinals"

**Solution**: Already fixed with the team name normalization from previous issue

## How the /live Page Works

### Backend `/live_games` Endpoint
Returns games where:
1. `game_date <= NOW()` (has started)
2. `winning_team IS NULL` (no winner yet)

### Frontend `Live.jsx`
1. Fetches from `/live_games` endpoint
2. Fetches live scores from `/api/gamescores` (CBS Sports)
3. Matches the two using team names
4. Displays matched games with live scores

## Diagnostic Steps

### Step 1: Check if Game Exists in Database
1. Navigate to Admin Games page
2. Search for "Virginia" or "Louisville"
3. Look for the game scheduled for today (October 4, 2025)

### Step 2: If Game EXISTS, Check Its Details
Look at:
- **Home Team**: Should be "Louisville" (or variation)
- **Away Team**: Should be "Virginia" (or variation)
- **Game Date**: Should be today (October 4, 2025) with correct start time
- **Winning Team**: Should be empty/NULL (game is not finished)

### Step 3: If Game DOES NOT EXIST
The game needs to be added to the database:

**Add via Admin Panel:**
1. Go to Admin Games page
2. Click "Add New Game"
3. Enter:
   - Home Team: `Louisville` (or `Louisville Cardinals`)
   - Away Team: `Virginia` (or `UVA` or `Virginia Cavaliers`)
   - Spread: (whatever the spread is)
   - Game Date: October 4, 2025, ~7:00 PM ET (or actual start time)
   - Winning Team: Leave empty

## Quick Fixes

### If Game is Missing from Database
```sql
INSERT INTO games (home_team, away_team, spread, game_date, winning_team)
VALUES ('Louisville', 'Virginia', 3.5, '2025-10-04 23:00:00+00', NULL);
-- Adjust spread and time as needed
```

### If Game Date is Wrong
```sql
UPDATE games 
SET game_date = '2025-10-04 23:00:00+00'  -- Adjust to correct UTC time
WHERE home_team ILIKE '%louisville%' AND away_team ILIKE '%virginia%';
```

### If Game Has Winner Set
```sql
UPDATE games 
SET winning_team = NULL
WHERE home_team ILIKE '%louisville%' AND away_team ILIKE '%virginia%';
```

## Expected Behavior After Fix

Once the game is properly in the database:

1. **Backend** `/live_games` will return it (because game_date <= NOW and winning_team is NULL)
2. **Frontend** will fetch it from `/live_games`
3. **Frontend** will fetch CBS Sports scores from `/api/gamescores`
4. **Frontend** will match "Virginia" with "Virginia" and "Louisville" with "Louisville"
5. **Live Page** will display: 
   ```
   Virginia 7 @ Louisville 7 (2nd 7:42)
   [Click to see picks]
   ```

## Summary

**Most Likely Issue**: The Virginia @ Louisville game **does not exist in your database**.

**Next Steps**:
1. Check Admin Games page to confirm
2. If missing, add the game via Admin panel
3. If exists but not showing, check game_date and winning_team fields
4. After fixing, refresh the /live page (wait 30 seconds for cache)

## Files Reference
- Backend endpoint: `march_madness_backend/main.py` (lines 1794-1826)
- Frontend page: `march-madness-frontend/src/pages/Live.jsx`
