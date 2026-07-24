# Auto-resolve games (CBS → spread / push)

Unresolved games are graded when CBS’s compact scoreboard shows the matchup as **Final** and team names match (same logic as the Live page).

## Behavior

- Only games with **no** `winning_team` and **scheduled start in the past** are considered.
- **Cover vs win:** `winning_team` is the side that **covered** (or `PUSH`), using the same spread rules as the app (`spread > 0` → home favored; `spread < 0` → away favored).
- Successful auto-resolve sets `auto_resolved_at` on the game document. Admins can still change the result via **PUT `/games/{id}`** if needed.

## Backend configuration (Vercel)

1. Generate a long random secret, e.g. `openssl rand -hex 32` (minimum **16 characters**; the API returns 503 if shorter or unset).
2. In the **backend** Vercel project → Settings → Environment Variables:
   - `CRON_SECRET` = that value (Production + Preview if you want previews to support cron).

## GitHub Actions (schedule)

Vercel **Hobby** cron only runs **once per day**, so scheduling uses this repo’s workflow.

1. Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:
   - **`AUTO_RESOLVE_BACKEND_URL`** — production API origin only, e.g. `https://your-backend.vercel.app` (no trailing slash).
   - **`CRON_SECRET`** — **same** string as `CRON_SECRET` on Vercel.

2. Workflow: `.github/workflows/auto-resolve-games.yml`  
   - Triggers every **5 minutes** (GitHub’s practical minimum for `schedule`).
   - **Eastern peak (1:30pm → 12:59am):** calls auto-resolve on **every** run (~5 min).
   - **Off-peak (1:00am → 1:29pm Eastern):** calls auto-resolve only when the minute is **:00** in `America/New_York` (~hourly).
   - **Actions** tab → **Auto-resolve games** → **Run workflow** to test manually.

If secrets are missing, the workflow fails with a clear message.

### Why not every 30 seconds?

GitHub Actions **cannot** run scheduled workflows every 30 seconds (shortest interval is on the order of **5 minutes**). To poll about **every 30s during games**, use a free external cron (e.g. **cron-job.org**, **EasyCron**) during your desired hours only:

- URL: `POST https://<your-backend>/internal/auto-resolve-games`
- Header: `Authorization: Bearer <CRON_SECRET>`
- Schedule: every 30s, time window **1:30pm–1:00am Eastern** (configure in the service’s timezone or UTC equivalent).

You can keep the GitHub workflow for off-peak hourly + backup peak coverage, or pause external jobs when not needed.

## Local test

```bash
export CRON_SECRET=your-secret
# Run API locally, then:
curl -sS -X POST "http://localhost:8000/internal/auto-resolve-games" \
  -H "Authorization: Bearer $CRON_SECRET"
```

Alternative header: `X-Cron-Secret: <secret>`.

## Response shape

JSON includes `resolved_count`, `resolved` (list of `{ game_id, winning_team, home_score, away_score }`), and `cbs_games_seen`.

## Limits

- Resolution speed depends on when CBS marks the game **Final** and on the schedule (GitHub ~5 min in peak, hourly off-peak, unless you add a faster external cron).
- Wrong or ambiguous team names vs CBS can prevent a match; use **Admin → Games** to resolve manually.
