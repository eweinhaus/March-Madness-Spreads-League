# Local development

## 1. Firebase project setup

1. Create a project at [Firebase Console](https://console.firebase.google.com/).
2. Enable **Firestore** (production mode is fine; rules deny client access).
3. Enable **Authentication → Google** sign-in provider.
4. Register a **Web app** and copy config values into `march-madness-frontend/.env.local`.
5. Create a **service account** (Project settings → Service accounts → Generate new private key) for the backend.

## 2. Backend environment

```bash
cd march_madness_backend
cp .env.example .env
```

Fill in `.env`:

| Variable | Description |
|----------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to downloaded service account JSON (local dev) |
| `LEAGUE_ID` | League identifier (default `football_2026`) |
| `FRONTEND_URL` | `http://localhost:5173` |

Alternatively set `FIREBASE_SERVICE_ACCOUNT_JSON` to the entire JSON on one line (typical for Vercel).

Start the API:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

Health check: `GET http://localhost:8000/health`

## 3. Frontend environment

```bash
cd march-madness-frontend
cp .env.example .env.local
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8000` and all `VITE_FIREBASE_*` values from the Firebase web app config.

## 4. Optional: Firebase emulators

Uncomment emulator host vars in `.env.example`, then:

```bash
firebase emulators:start
```

## 5. Make a user admin

After signing in once (creates the Firestore user doc):

```bash
python scripts/make_admin.py <firebase-uid-or-email>
```

## 6. Auto-resolve cron (production)

For production auto-resolve, set matching secrets in Vercel and GitHub Actions. See [AUTO_RESOLVE.md](AUTO_RESOLVE.md).

## 7. Run tests

```bash
cd march_madness_backend
pip install pytest
pytest tests/ -q
```

```bash
cd march-madness-frontend
npm run lint
```

## Credentials safety

Never commit `.env`, `.env.local`, `.env.production`, or service account JSON files. If credentials are ever exposed, rotate the Firebase service account key immediately. See `march_madness_backend/CREDENTIALS.md`.
