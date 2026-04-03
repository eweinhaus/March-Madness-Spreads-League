#!/usr/bin/env bash
#
# Set up Cloud Monitoring alerts for Firestore usage (same project as Firebase).
# Sends email when daily reads >= 25,000 or daily writes >= 10,000.
#
# Prerequisites:
#   - Google Cloud CLI (gcloud) installed and logged in
#   - Project set to your Firebase project: gcloud config set project YOUR_PROJECT_ID
#
# Usage:
#   ./scripts/setup-firestore-usage-alerts.sh YOUR_EMAIL@example.com
#   ./scripts/setup-firestore-usage-alerts.sh YOUR_EMAIL@example.com [PROJECT_ID]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICIES_DIR="${SCRIPT_DIR}/alert-policies"

if [ -z "$1" ]; then
  echo "Usage: $0 YOUR_EMAIL@example.com [PROJECT_ID]"
  echo ""
  echo "Creates a Cloud Monitoring email notification channel and two alert policies:"
  echo "  - Firestore: 25k reads per day"
  echo "  - Firestore: 10k writes per day"
  echo ""
  echo "PROJECT_ID defaults to the current gcloud project."
  exit 1
fi

EMAIL="$1"
PROJECT_ID="${2:-$(gcloud config get-value project 2>/dev/null)}"

if [ -z "$PROJECT_ID" ]; then
  echo "Error: No project ID. Set with: gcloud config set project YOUR_FIREBASE_PROJECT_ID"
  exit 1
fi

echo "Project: $PROJECT_ID"
echo "Email:   $EMAIL"
echo ""

# Create email notification channel (idempotent: create; if already exists, list and use)
CHANNEL_NAME=""
EXISTING=$(gcloud alpha monitoring channels list --project="$PROJECT_ID" --filter="displayName:Firestore usage alerts" --format="value(name)" 2>/dev/null | head -1)
if [ -n "$EXISTING" ]; then
  echo "Using existing notification channel: $EXISTING"
  CHANNEL_NAME="$EXISTING"
else
  echo "Creating email notification channel..."
  CHANNEL_NAME=$(gcloud beta monitoring channels create \
    --project="$PROJECT_ID" \
    --display-name="Firestore usage alerts" \
    --type=email \
    --channel-labels=email_address="$EMAIL" \
    --format="value(name)" 2>/dev/null)
  if [ -z "$CHANNEL_NAME" ]; then
    echo "Failed to create channel. You may need to create one in the console:"
    echo "  https://console.cloud.google.com/monitoring/alerting/notifications?project=$PROJECT_ID"
    exit 1
  fi
  echo "Created channel: $CHANNEL_NAME"
fi

# Firebase will send a verification email; user must click the link
echo ""
echo "If this is a new channel, check $EMAIL and verify the notification channel."
echo ""

# Create alert policies with this notification channel
for POLICY_FILE in "${POLICIES_DIR}"/firestore-reads-25k.json "${POLICIES_DIR}"/firestore-writes-10k.json; do
  NAME=$(basename "$POLICY_FILE" .json)
  echo "Creating alert policy: $NAME"
  gcloud alpha monitoring policies create \
    --project="$PROJECT_ID" \
    --policy-from-file="$POLICY_FILE" \
    --notification-channels="$CHANNEL_NAME" \
    || echo "  (Policy may already exist; check console to update or delete and re-run)"
done

echo ""
echo "Done. Alerts:"
echo "  - Firestore: 25k reads per day  -> $EMAIL"
echo "  - Firestore: 10k writes per day -> $EMAIL"
echo ""
echo "View/edit: https://console.cloud.google.com/monitoring/alerting/policies?project=$PROJECT_ID"
