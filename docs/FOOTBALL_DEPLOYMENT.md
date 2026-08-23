# Football 2026 Deployment Guide

This guide walks through deploying the football season configuration to production.

## Prerequisites

- Backend deployed to Vercel (`spread-league-api`)
- Frontend deployed to Vercel (`spread-league-web`)
- Firebase project configured (`spread-league-21126`)
- Admin access to Vercel projects

## Deployment Steps

### 1. Update Backend Environment Variables (Vercel)

Navigate to the **Backend** Vercel project (`spread-league-api`):

1. Go to **Settings → Environment Variables**
2. Set or update these variables for **Production**:

   ```
   SPORT_MODE=football
   LEAGUE_ID=football_2026
   ```

3. Optional: Also set for **Preview** if you want branch deploys to use football mode

### 2. Redeploy Backend

After updating environment variables:

1. **Option A:** Trigger automatic redeploy
   - Go to **Deployments** tab
   - Click **⋮** (three dots) on latest production deployment
   - Select **Redeploy**
   - Check **Use existing build cache** (optional, for faster deploy)

2. **Option B:** Push a commit to `main` branch (triggers automatic deploy)

### 3. Verify Backend Configuration

Once backend redeploys, test the `/app-config` endpoint:

```bash
curl https://spread-league-api.vercel.app/app-config
```

Expected response:

```json
{
  "sport_mode": "football",
  "display_name": "Football Season 2026",
  "season_label": "2026 Season",
  "pick_noun": "game",
  "period_type": "week"
}
```

### 4. Update Frontend Environment Variables (Vercel)

Navigate to the **Frontend** Vercel project (`spread-league-web`):

1. Go to **Settings → Environment Variables**
2. Set or update these variables for **Production** (if not already set):

   ```
   VITE_SPORT_MODE=football
   ```

   Note: Frontend primarily uses backend `/app-config`, but this fallback ensures resilience.

### 5. Redeploy Frontend

Same process as backend:

1. Go to **Deployments** → **Redeploy** latest production, OR
2. Push commit to trigger automatic deploy

### 6. Verify Frontend

Visit production frontend: `https://spread-league-web.vercel.app`

Check:
- [ ] Page title shows "Spread Pools - Football 2026"
- [ ] Favicon shows football icon (brown football on green circle)
- [ ] Home page mentions "Football Season 2026"
- [ ] Loading spinners show football icon (not basketball)

### 7. Reset Firestore Data (One-Time)

**⚠️ WARNING:** This wipes all production data. Only proceed if ready for a clean season start.

1. **Backup** (optional): Export Firestore data if you want to preserve old season
2. Run reset script from local machine with production credentials:

   ```bash
   cd /workspace
   # Ensure .env has production Firebase credentials
   export LEAGUE_ID=football_2026
   python scripts/reset_season.py
   ```

3. Type exactly: `RESET football_2026` when prompted

4. Verify all collections are empty in Firebase Console → Firestore

See [docs/RESET_SEASON.md](RESET_SEASON.md) for detailed reset instructions.

### 8. Re-Promote Admin Users

After Firestore wipe, all users are deleted. Re-promote admins:

```bash
python scripts/make_admin.py <firebase-uid>
```

Get Firebase UIDs from:
- Firebase Console → Authentication → Users
- Have admins sign in, then check Firestore → `users` collection

Example:

```bash
# Ethan Weinhaus
python scripts/make_admin.py xc7KvlCV8oN4R3STgRVrBEmuJbq1
```

### 9. Smoke Test

As an admin:

1. Sign in to production frontend
2. Navigate to **Admin → Games**
3. Create a test game (e.g., Week 1 NFL game)
4. As a regular user (or different account), submit a pick
5. Admin resolves the game with a final score
6. Check **Leaderboard** shows updated points

### 10. Announce to Users

Once verified:
- Notify league members the new season is live
- Share production URL: `https://spread-league-web.vercel.app`
- Remind users to sign in with their existing Google accounts

## Rollback Plan

If issues arise after deployment:

### Backend Rollback

1. Vercel → **Backend** → **Deployments**
2. Find last known-good deployment
3. Click **⋮** → **Promote to Production**

### Frontend Rollback

Same process for frontend project.

### Environment Variable Revert

1. Change `SPORT_MODE` and `LEAGUE_ID` back to previous values
2. Redeploy both backend and frontend

## Monitoring

After deployment, monitor:

- **Vercel Logs**: Check for runtime errors
- **Firebase Console**: Verify game creation, pick submission working
- **User Reports**: Watch for authentication or data issues

## Troubleshooting

### Frontend shows basketball icons

- Check backend `/app-config` returns `"sport_mode": "football"`
- Clear browser cache and hard refresh (Cmd/Ctrl + Shift + R)
- Check Vercel frontend logs for errors fetching config

### Backend /app-config returns wrong sport_mode

- Verify `SPORT_MODE=football` is set in Vercel backend env vars
- Ensure backend redeployed after env var change
- Check Vercel **Deployments** → latest → **Environment Variables** tab

### Users can't sign in after reset

- Ensure Firebase Auth accounts still exist (reset only wipes Firestore, not Auth)
- Check Firestore rules are deployed (`firestore.rules`)
- Verify backend can reach Firebase (check Vercel logs)

### Admin can't create games

- Verify admin re-promoted via `scripts/make_admin.py` after reset
- Check Firestore → `users` → admin user has `"admin": true`
- Try sign out / sign in to refresh ID token

## Custom Domain (Optional)

If you want to use `spreadpools.com` instead of Vercel URLs:

1. Purchase domain (e.g., Namecheap, Google Domains)
2. Vercel → **Frontend** → **Settings → Domains** → **Add**
3. Follow DNS configuration steps
4. Update `PRODUCTION_FRONTEND_URL` backend env var to match custom domain
5. Update Firebase authorized domains (Firebase Console → Authentication → Settings → Authorized domains)

## See Also

- [docs/RESET_SEASON.md](RESET_SEASON.md) - Detailed reset instructions
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and configuration
- [march_madness_backend/.env.example](../march_madness_backend/.env.example) - All env vars
