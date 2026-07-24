# Architecture

## System overview

Spread Pools is a full-stack spread-picking league app. Users authenticate with Google via Firebase Auth, interact with a React SPA, and all data flows through a FastAPI backend that owns Firestore access.

```
┌─────────────┐     Google OAuth      ┌──────────────┐
│   Browser   │ ────────────────────► │ Firebase Auth│
│  (React SPA)│                       └──────────────┘
└──────┬──────┘
       │ Firebase ID token (Bearer)
       ▼
┌─────────────┐     Admin SDK         ┌──────────────┐
│   FastAPI   │ ────────────────────► │  Firestore   │
│  (Vercel)   │                       │  collections │
└──────┬──────┘                       └──────────────┘
       │
       │ POST /internal/auto-resolve-games (CRON_SECRET)
       ▼
┌─────────────┐
│GitHub Actions│ ──► CBS scoreboard scrape ──► cover/push grading
└─────────────┘
```

## Firestore collections

| Collection | Purpose |
|------------|---------|
| `users` | App profile keyed by Firebase UID (admin flag, league, display name) |
| `games` | Matchups with spread, schedule, scores, winning team |
| `picks` | User picks per game (optional lock-of-the-day `*` suffix) |
| `tiebreaker_picks` | Bonus tiebreaker answers |
| `leaderboard` | Cached total points per user |
| `_cache` | Leaderboard/live/stats response caches |

## Security model

- **Firestore rules** (`firestore.rules`): deny all client reads and writes.
- **Backend**: verifies Firebase ID tokens on every authenticated route; admin routes require `admin: true` on the user document.
- **Cron endpoint**: `/internal/auto-resolve-games` requires `Authorization: Bearer <CRON_SECRET>` (minimum 16 characters).
- **Secrets**: never committed; see `march_madness_backend/.env.example` and `CREDENTIALS.md`.

## Scoring rules

Spread convention (in `scoring.py`):

- `spread > 0` — home team favored by that many points
- `spread < 0` — away team favored by `|spread|`
- `spread == 0` — pick'em (straight winner; tie = push)

Pick points:

- Correct pick: **1 point**
- Correct lock-of-the-day (`*`): **2 points**
- Push: **0 points** for all picks on that game

## Pick locking

- Individual games lock **1 minute before tip-off**.
- Lock-of-the-day uses an ET window: **3:00 AM ET → next day 3:00 AM ET** (one lock per calendar "day" in league time).

## Auto-resolve pipeline

During tournament windows, GitHub Actions calls the backend every ~5 minutes (peak hours) or hourly (off-peak). The backend:

1. Fetches unresolved games whose start time is in the past
2. Scrapes CBS Sports compact scoreboard
3. Matches team names (fuzzy + normalized)
4. Computes covering team from final score + spread
5. Updates game, re-scores picks, and invalidates leaderboard cache

Details: [AUTO_RESOLVE.md](AUTO_RESOLVE.md)

## Deployment

| Component | Host |
|-----------|------|
| Frontend SPA | Vercel (`march-madness-frontend/`) |
| Backend API | Vercel (`march_madness_backend/`) |
| Database / Auth | Firebase |
| Scheduled jobs | GitHub Actions (`.github/workflows/auto-resolve-games.yml`) |

## Migration history

The app originally ran on **Render + PostgreSQL + JWT auth**. It was migrated to **Vercel + Firestore + Google OAuth** with a fresh database (logical schema preserved, data wiped). This demonstrates an incremental platform migration under a live product.
