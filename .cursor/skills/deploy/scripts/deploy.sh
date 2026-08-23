#!/usr/bin/env bash
# Deploy Spread Pools frontend + backend to Vercel production.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
FRONT="$ROOT/march-madness-frontend"
API="$ROOT/march_madness_backend"

if ! command -v vercel >/dev/null 2>&1; then
  echo "error: vercel CLI not found. Install: npm i -g vercel" >&2
  exit 1
fi

echo "==> Auth: $(vercel whoami)"
echo "==> Deploying frontend (spread-league-web)..."
(
  cd "$FRONT"
  vercel deploy --prod --yes
)

echo "==> Deploying backend (spread-league-api)..."
(
  cd "$API"
  vercel deploy --prod --yes
)

echo "==> Verifying..."
FRONT_CODE="$(curl -sS -o /dev/null -w '%{http_code}' https://spreadpools.com/ || true)"
API_BODY="$(curl -sS https://spread-league-api.vercel.app/health || true)"

echo "Frontend https://spreadpools.com/ → HTTP ${FRONT_CODE}"
echo "API https://spread-league-api.vercel.app/health → ${API_BODY}"

if [[ "$FRONT_CODE" != "200" ]]; then
  echo "warning: frontend did not return 200" >&2
fi
if [[ -z "$API_BODY" ]]; then
  echo "warning: API health check empty/failed" >&2
fi

echo "Done."
