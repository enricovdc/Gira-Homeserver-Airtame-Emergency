#!/usr/bin/env bash
# Smoke-test the Airtame Emergency Alerts endpoint with the same payload
# shape the module sends. Use this to verify your API key works before
# wiring the module into a production logic page.
#
# Usage:
#   AIRTAME_API_KEY=xxx ./examples/curl_initiate.sh
set -euo pipefail

: "${AIRTAME_API_KEY:?set AIRTAME_API_KEY to your Airtame Cloud API key}"

ALERT_ID="${ALERT_ID:-curl-smoke-$(date -u +%Y%m%dT%H%M%SZ)}"
EXPIRES_AT="$(date -u -d '+5 minutes' +%Y-%m-%dT%H:%M:%S+00:00 2>/dev/null \
            || date -u -v+5M +%Y-%m-%dT%H:%M:%S+00:00)"

curl -sS --fail-with-body \
    -u "gira:${AIRTAME_API_KEY}" \
    -H 'Content-Type: application/json' \
    -X POST 'https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts' \
    -d @- <<JSON
{
  "id": "${ALERT_ID}",
  "status": "Initiated",
  "template": "high",
  "headline": "Test alert",
  "description": "Manual smoke test from curl.",
  "isDrill": true,
  "expiresAt": "${EXPIRES_AT}"
}
JSON
echo
echo "Initiated alert id: ${ALERT_ID}"
