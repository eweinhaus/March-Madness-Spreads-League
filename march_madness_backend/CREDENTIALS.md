# Credentials and production config

- **Do not commit** `.env`, `.env.production`, or any file containing `FIREBASE_SERVICE_ACCOUNT_JSON` or private keys.
- Configure production in **Vercel → Project → Settings → Environment Variables** (`FIREBASE_SERVICE_ACCOUNT_JSON`, `CRON_SECRET`, etc.).
- **`CRON_SECRET`**: use a long random value (≥16 characters). Set the same value in GitHub Actions secret `CRON_SECRET` for auto-resolve workflows.

## If credentials were ever in git or shared

1. **Firebase**: Google Cloud Console → IAM → Service Accounts → your Firebase admin SA → **Keys** → delete the compromised key → **Add key** → update Vercel env with the new JSON.
2. **GitHub / chat leaks**: assume the old key is burned; rotation is mandatory.
