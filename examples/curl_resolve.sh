#!/usr/bin/env bash
set -euo pipefail

: "${AIRTAME_API_KEY:?set AIRTAME_API_KEY to your Airtame Cloud API key}"
: "${1:?usage: $0 <alert-id>}"

curl -sS --fail-with-body \
    -u "gira:${AIRTAME_API_KEY}" \
    -H 'Content-Type: application/json' \
    -X POST 'https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts' \
    -d "{\"id\":\"$1\",\"status\":\"Resolved\"}"
echo
