# Season Reset Guide

This guide explains how to safely reset Firestore data for a new season.

## ⚠️ Warning

**This process is irreversible.** All user accounts, game data, picks, and leaderboard history will be permanently deleted from Firestore.

## Prerequisites

- Backend environment variables configured (`.env` file or Vercel secrets)
- Python 3.9+ with `firebase-admin` installed
- Firebase Admin SDK credentials (same as backend uses)

## Before You Begin

### 1. Optional: Export Backup

If you want to preserve historical data, export Firestore collections first:

```bash
# Using gcloud CLI (requires Firebase project permissions)
gcloud firestore export gs://[YOUR-BUCKET]/[BACKUP-FOLDER]
```

### 2. Verify Configuration

Ensure `LEAGUE_ID` matches the season you're resetting:

```bash
cd march_madness_backend
cat .env | grep LEAGUE_ID
# Should show: LEAGUE_ID=football_2026 (or your target season)
```

## Reset Procedure

### Step 1: Run the Reset Script

From the repo root:

```bash
cd /workspace
python scripts/reset_season.py
```

The script will:
1. Display current `LEAGUE_ID`
2. List collections to be deleted
3. Prompt for confirmation: you must type exactly `RESET {league_id}`

**Example:**

```
SPREAD POOLS SEASON RESET SCRIPT
============================================================

Current LEAGUE_ID: football_2026

This will DELETE ALL DATA from the following collections:
  - users
  - games
  - picks
  - tiebreakers
  - tiebreaker_picks
  - leaderboard
  - _cache

⚠️  THIS ACTION IS IRREVERSIBLE ⚠️

To confirm, type exactly: RESET football_2026
> RESET football_2026

🔥 Starting deletion...
```

### Step 2: Re-Promote Admin Users

After reset, **all user documents are deleted**. Re-promote admins:

```bash
cd /workspace
python scripts/make_admin.py <firebase-uid>
```

Get Firebase UIDs from:
- Firebase Console → Authentication → Users
- Ask users to sign in once, then check Firestore → users collection for their `uid`

### Step 3: Verify Clean State

- Visit the frontend (e.g., `http://localhost:5173` or production URL)
- Sign in with Google
- Check that user is created fresh (no old picks/data)
- Admin can now create games for the new season

## What Gets Deleted

| Collection | Contents |
|------------|----------|
| `users` | All user profiles and admin flags |
| `games` | All matchups, scores, and results |
| `picks` | All user picks (including lock-of-the-day) |
| `tiebreakers` | All tiebreaker questions |
| `tiebreaker_picks` | All tiebreaker answers |
| `leaderboard` | Cached leaderboard totals |
| `_cache` | API response caches |

## What Does NOT Get Deleted

- Firebase Auth accounts (users can still sign in with same Google account)
- Firebase project configuration
- Backend code/deployments
- Firestore indexes/rules

## Troubleshooting

### "No Firebase credentials found"

Ensure one of these is set in your environment:

- `GOOGLE_APPLICATION_CREDENTIALS` pointing to service account JSON file
- `FIREBASE_SERVICE_ACCOUNT_JSON` with inline JSON (Vercel style)

### "Confirmation did not match"

Type the confirmation **exactly** as shown, including capitalization and the league ID.

### Partial Delete Failure

If a collection fails mid-delete, the script will note it but continue. You can:
1. Re-run the script (safe; only deletes remaining docs)
2. Manually delete remaining docs in Firebase Console

## Production Reset Checklist

Before resetting production Firestore:

- [ ] Announce downtime to users (if applicable)
- [ ] Export backup if desired
- [ ] Verify `LEAGUE_ID` in production backend env vars (Vercel)
- [ ] Run reset script with production credentials
- [ ] Re-promote all admin users
- [ ] Admin creates first test game
- [ ] Smoke test: user signs in, makes pick, views leaderboard
- [ ] Announce new season is live

## See Also

- `scripts/make_admin.py` - Promote users to admin
- `docs/ARCHITECTURE.md` - System architecture and data model
- `march_madness_backend/.env.example` - Required environment variables
