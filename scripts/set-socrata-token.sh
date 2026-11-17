#!/bin/bash
# Save a NYC Open Data app token as the SOCRATA_APP_TOKEN repository secret, so the
# nightly refresh isn't throttled as an anonymous GitHub machine. Safe to re-run.
#
# Needs: gh signed in (gh auth login) with admin access to the repo.
# Get a token: sign in at data.cityofnewyork.us, then Developer Settings > Create New App Token.
# Usage: scripts/set-socrata-token.sh          paste the app token when asked
#        SOCRATA_APP_TOKEN=... scripts/set-socrata-token.sh
set -euo pipefail
cd "$(dirname "$0")/.."

REPO=${REPO:-amanda-nathan/bike-lane-lakehouse}
TOKEN_PAGE=https://data.cityofnewyork.us/profile/edit/developer_settings

TOKEN=${SOCRATA_APP_TOKEN:-}
if [ -z "$TOKEN" ]; then
  echo "Create an app token at $TOKEN_PAGE (copy the App Token, not the Secret Token)."
  command -v open >/dev/null && open "$TOKEN_PAGE"
  read -rsp "App token: " TOKEN
  echo
fi
[ -n "$TOKEN" ] || { echo "No token given." >&2; exit 1; }

# A bad token gets a 403; a good one returns one row from the crashes dataset.
status=$(curl -s -o /dev/null -w '%{http_code}' -H "X-App-Token: $TOKEN" \
  'https://data.cityofnewyork.us/resource/h9gi-nx95.json?$limit=1')
if [ "$status" != 200 ]; then
  echo "NYC Open Data rejected the token (HTTP $status). Check you copied the App Token." >&2
  exit 1
fi

gh secret set SOCRATA_APP_TOKEN --repo "$REPO" --body "$TOKEN"
echo "Saved SOCRATA_APP_TOKEN on $REPO. The next refresh run will use it."
