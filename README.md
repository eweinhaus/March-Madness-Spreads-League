# Spread Pools

Production full-stack web app for managing multi-user sports spread-picking leagues. Used by **40+ active players** across multiple sports and tournaments.

**Live demo:** [spreadpools.com](https://www.spreadpools.com)

## Highlights

- **React + Vite** frontend with Firebase Auth (Google OAuth)
- **FastAPI** backend on Vercel with Firebase Admin SDK (server-only Firestore access)
- **Automated scoring** — GitHub Actions cron triggers CBS scoreboard scraping to resolve cover/push results
- **Real-time leaderboards** with Firestore-backed caching and lock-of-the-day pick rules
- **Admin tools** for game management, tiebreakers, and user pick oversight

## Architecture

```
Browser (React) ──► Firebase Auth (Google OAuth)
       │
       └──► FastAPI (Vercel) ──► Firestore (Admin SDK, client rules deny all)
                    │
                    └──► CBS scoreboard scrape (auto-resolve cron)
```

| Layer | Technology |
|-------|------------|
| Frontend | React, Vite, React Bootstrap, Firebase client SDK |
| Backend | Python, FastAPI, BeautifulSoup |
| Database | Firebase Firestore |
| Auth | Firebase Auth (Google OAuth) |
| Hosting | Vercel (frontend + backend) |
| CI / Cron | GitHub Actions |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for data model, security model, and auto-resolve pipeline details.

## Local development

### Prerequisites

- Node.js 18+
- Python 3.9+
- A Firebase project with Firestore and Google sign-in enabled

### Backend

```bash
cd march_madness_backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in Firebase credentials
./start.sh                  # http://localhost:8000
```

### Frontend

```bash
cd march-madness-frontend
npm install
cp .env.example .env.local  # Firebase web config + VITE_API_URL
npm run dev                 # http://localhost:5173
```

Full setup (emulators, Vercel env vars, cron secrets): [docs/LOCAL_DEV.md](docs/LOCAL_DEV.md)

## Tests

```bash
cd march_madness_backend
pip install pytest
pytest tests/ -q
```

CI runs backend unit tests and frontend ESLint on every push to `main`.

## Project structure

```
march-madness-frontend/   React SPA (Vercel)
march_madness_backend/    FastAPI API (Vercel)
docs/                     Architecture and ops guides
.github/workflows/        CI and auto-resolve cron
firestore.rules           Deny all client Firestore access
scripts/                  Admin utilities
```

## Interview talking points

- Migrated a live app from **Render + PostgreSQL** to **Vercel + Firestore** without downtime for users
- Built a **reliable auto-resolve pipeline** (peak/off-peak cron, CBS scraping, cover/push logic)
- Enforced **fail-closed security** — Firestore rules deny all client reads/writes; backend uses Admin SDK
- Operated under real usage (**40+ users**) including scoring bug fixes with validation and rollback planning

## License

MIT — see [LICENSE](LICENSE).
