# Live Score Matching Issue - Vanderbilt vs Alabama

## Issue Summary
The app is having trouble matching live scores from CBS Sports to games in the database, specifically for the Vanderbilt vs Alabama game.

## Investigation Results

### CBS Sports Team Names (Confirmed)
From the CBS Sports scoreboard (`https://www.cbssports.com/college-football/scoreboard/?layout=compact`):
- **Away Team**: `'Vanderbilt'`
- **Home Team**: `'Alabama'`
- **Format**: Short team names without mascots

### Database Team Names (Likely Format)
Based on typical sports database patterns, the database likely stores teams as:
- **Full Names**: `'Vanderbilt Commodores'` and `'Alabama Crimson Tide'`
- **OR Variations**: Different capitalization, abbreviations, or alternate names

## Root Cause Analysis

The matching issue occurs in two places:

### 1. Frontend Matching Logic (`Live.jsx`)
The frontend has a `normalizeTeamName()` function (lines 268-300) that handles some variations:
- `St.` → `State` or `Saint`
- Directional abbreviations (`W.`, `E.`, `N.`, `So.`)
- State abbreviations (`Tenn`, `Fla`, `Ark`)

**MISSING**: The function does NOT handle:
- Full team names with mascots (e.g., "Alabama Crimson Tide" → "Alabama")
- Common variations like "Vandy" → "Vanderbilt"
- Partial matching for full team names

### 2. Backend Scraping Logic (`main.py`)
Lines 2889-2895 extract team names from CBS Sports:
```python
away_team = team_cells[0].find('a', class_='team-name-link').text.strip()
home_team = team_cells[1].find('a', class_='team-name-link').text.strip()
```

This correctly extracts `'Vanderbilt'` and `'Alabama'`, but there's no normalization before matching against the database.

## Comparison with Working Games

From the CBS Sports output, these teams ARE working:
- `'UTSA'`, `'Temple'`, `'Wake Forest'`, `'Virginia Tech'`, etc.

This suggests the database either:
1. Has exact matches for these teams (stored as "UTSA", not "UTSA Roadrunners")
2. OR the matching logic works for some teams but not others

## Recommended Solutions

### Solution 1: Enhance Frontend Team Name Normalization (Recommended)
Update the `normalizeTeamName()` function in `Live.jsx` to:
1. Strip common mascot names (Crimson Tide, Commodores, etc.)
2. Handle partial matches better
3. Add common team name variations

### Solution 2: Add Backend Team Name Mapping
Create a mapping dictionary in the backend for problematic teams:
```python
TEAM_NAME_MAPPING = {
    'vanderbilt': ['vanderbilt', 'vandy', 'vanderbilt commodores'],
    'alabama': ['alabama', 'bama', 'alabama crimson tide'],
    # ... more teams
}
```

### Solution 3: Improve Database Team Names
Standardize database team names to match CBS Sports format (short names without mascots).

## Testing Needed

To confirm the exact issue, we need to:
1. ✅ Check CBS Sports team name format → **CONFIRMED**: `'Vanderbilt'` and `'Alabama'`
2. ⏳ Check database team name format for this specific game
3. ⏳ Test the matching logic with both team name formats

## Files to Modify

1. **`march-madness-frontend/src/pages/Live.jsx`** (Lines 268-314)
   - Enhance `normalizeTeamName()` function
   - Improve `teamNamesMatch()` function

2. **`march_madness_backend/main.py`** (Lines 2855-2924)
   - Add team name normalization/mapping for CBS Sports data
   - Improve matching logic

## Priority
**HIGH** - Affects live game tracking for users during active games.
