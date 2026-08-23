# Auto-resolve games (CBS → spread / push)

**⚠️ DEPRECATED:** This auto-resolve pipeline is no longer active as of PRD-01 (Football Foundation).

Admins now manually enter final scores and results via the **Admin Games UI** instead of relying on automated CBS scraping. The GitHub Actions workflow has been disabled, and the `/internal/auto-resolve-games` endpoint returns early with a deprecation message.

---

## Why Deprecated

The auto-resolve system based on CBS scraping was unreliable:
- Team name matching failures
- CBS scoreboard delays or incorrect "Final" status
- Maintenance overhead for scraping logic updates

Manual admin entry provides more control and reliability.

---

## Historical Behavior (Reference Only)

This section documents the original auto-resolve system, preserved for reference but no longer in use.

### Original Concept

Unresolved games were graded when CBS's compact scoreboard showed the matchup as **Final** and team names matched (same logic as the Live page).

### Behavior

- Only games with **no** `winning_team` and **scheduled start in the past** were considered.
- **Cover vs win:** `winning_team` is the side that **covered** (or `PUSH`), using the same spread rules as the app (`spread > 0` → home favored; `spread < 0` → away favored).
- Successful auto-resolve set `auto_resolved_at` on the game document. Admins could still change the result via **PUT `/games/{id}`** if needed.

### Backend configuration (Vercel)

1. Generate a long random secret, e.g. `openssl rand -hex 32` (minimum **16 characters**; the API returns 503 if shorter or unset).
2. In the **backend** Vercel project → Settings → Environment Variables:
   - `CRON_SECRET` = that value (Production + Preview if you want previews to support cron).

### GitHub Actions (schedule)

Vercel **Hobby** cron only runs **once per day**, so scheduling used this repo's workflow.

1. Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:
   - **`AUTO_RESOLVE_BACKEND_URL`** — production API origin only, e.g. `https://your-backend.vercel.app` (no trailing slash).
   - **`CRON_SECRET`** — **same** string as `CRON_SECRET` on Vercel.

2. Workflow: `.github/workflows/auto-resolve-games.yml` (now disabled)
   - Triggered every **5 minutes** (GitHub's practical minimum for `schedule`).
   - **Eastern peak (1:30pm → 12:59am):** called auto-resolve on **every** run (~5 min).
   - **Off-peak (1:00am → 1:29pm Eastern):** called auto-resolve only when the minute was **:00** in `America/New_York` (~hourly).
   - **Actions** tab → **Auto-resolve games** → **Run workflow** to test manually.

If secrets were missing, the workflow failed with a clear message.

### Why not every 30 seconds?

GitHub Actions **cannot** run scheduled workflows every 30 seconds (shortest interval is on the order of **5 minutes**). To poll about **every 30s during games**, use a free external cron (e.g. **cron-job.org**, **EasyCron**) during your desired hours only:

- URL: `POST https://<your-backend>/internal/auto-resolve-games`
- Header: `Authorization: Bearer <CRON_SECRET>`
- Schedule: every 30s, time window **1:30pm–1:00am Eastern** (configure in the service's timezone or UTC equivalent).

You could keep the GitHub workflow for off-peak hourly + backup peak coverage, or pause external jobs when not needed.

### Local test

```bash
export CRON_SECRET=your-secret
# Run API locally, then:
curl -sS -X POST "http://localhost:8000/internal/auto-resolve-games" \
  -H "Authorization: Bearer $CRON_SECRET"
```

Alternative header: `X-Cron-Secret: <secret>`.

### Response shape

JSON included `resolved_count`, `resolved` (list of `{ game_id, winning_team, home_score, away_score }`), and `cbs_games_seen`.

### Limits

- Resolution speed depended on when CBS marked the game **Final** and on the schedule (GitHub ~5 min in peak, hourly off-peak, unless you added a faster external cron).
- Wrong or ambiguous team names vs CBS could prevent a match; use **Admin → Games** to resolve manually.
