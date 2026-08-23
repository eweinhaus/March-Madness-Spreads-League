---
name: deploy
description: >-
  Deploy Spread Pools (March Madness Spreads League) frontend and backend to
  Vercel production. Use when the user says /deploy, asks to deploy, ship to
  production, or push the app live on Vercel.
disable-model-invocation: true
---

# /deploy — Vercel production deploy

Deploys **both** Vercel projects for this repo to production. Do not stop after one project.

## Projects

| Dir | Vercel project | Production URL |
|-----|----------------|----------------|
| `march-madness-frontend/` | `spread-league-web` | https://spreadpools.com |
| `march_madness_backend/` | `spread-league-api` | https://spread-league-api.vercel.app |

Each directory already has `.vercel/project.json`. Deploy from that directory so linking stays correct.

## Steps (run every time)

1. Confirm Vercel CLI auth (needs network + unrestricted shell; sandbox breaks auth/cache):

```bash
vercel whoami
```

2. Prefer the repo script (deploys both, prints URLs, checks `/health`):

```bash
bash .cursor/skills/deploy/scripts/deploy.sh
```

3. If the script is unavailable, deploy manually **in order** (frontend then API), with `--yes` and full permissions:

```bash
cd march-madness-frontend && vercel deploy --prod --yes
cd ../march_madness_backend && vercel deploy --prod --yes
```

4. Verify:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://spreadpools.com/
curl -sS https://spread-league-api.vercel.app/health
```

Expect frontend `200` and API JSON including a healthy status.

5. Reply with both production URLs (and inspect URLs from the CLI output if useful). Do not commit or push unless the user asks.

## Rules

- Always production (`--prod`). Do not create a new Vercel project or run `vercel link` unless linking is broken.
- Do not change env vars during deploy unless the user asks.
- Shell: request unrestricted permissions (`all`) so Vercel CLI can reach the network and write its cache.
- If auth fails, tell the user to run `vercel login` locally; do not invent tokens.
- Optional scope: if the user says **frontend only** or **backend only**, deploy just that directory.

## Env (do not redeploy to “fix” missing secrets)

Frontend Vercel: `VITE_API_URL`, `VITE_FIREBASE_*`  
Backend Vercel: `FIREBASE_SERVICE_ACCOUNT_JSON` (or credentials), `FRONTEND_URL` / `PRODUCTION_FRONTEND_URL`, `LEAGUE_ID`, `CRON_SECRET`

Ops detail: `docs/LOCAL_DEV.md`, `docs/VERCEL_MIGRATION.md`, `docs/AUTO_RESOLVE.md`.
