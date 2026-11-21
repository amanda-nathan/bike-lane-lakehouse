#!/bin/bash
# Delete the read-only R2 key that the public MCP server used, and comment it out of .env.
# Run this when the server is shut down, so a key nobody needs can't be used. Safe to re-run.
#
# Needs: R2_READ_TOKEN and R2_ENDPOINT in .env. If Cloudflare won't let the key delete itself,
# also a Cloudflare API token with "Account API Tokens: Edit" as CLOUDFLARE_API_TOKEN.
# Usage: scripts/revoke-r2-read-key.sh
#        CLOUDFLARE_API_TOKEN=... scripts/revoke-r2-read-key.sh
# A new read-only key for a redeploy: R2 > Manage API tokens > Create API token, Object Read only.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; source .env; set +a
API=https://api.cloudflare.com/client/v4
# The endpoint is https://<account-id>.r2.cloudflarestorage.com
ACCOUNT=$(sed -E 's#https://([^.]+)\..*#\1#' <<<"${R2_ENDPOINT:?R2_ENDPOINT missing from .env}")

comment_out_env() {
  sed -i.bak -E 's/^(R2_READ_(TOKEN|ACCESS_KEY_ID|SECRET_ACCESS_KEY)=)/# revoked: \1/' .env
  rm -f .env.bak
  echo "Commented out the R2_READ_* lines in .env."
}

if [ -z "${R2_READ_TOKEN:-}" ]; then
  echo "No R2_READ_TOKEN in .env; nothing to delete."
  exit 0
fi

# Verifying the key tells us its ID, and whether it still works.
ID=$(curl -s -H "Authorization: Bearer $R2_READ_TOKEN" "$API/accounts/$ACCOUNT/tokens/verify" |
  python3 -c 'import sys, json; d = json.load(sys.stdin); print(d["result"]["id"] if d.get("success") else "")')
if [ -z "$ID" ]; then
  echo "Cloudflare no longer accepts the key, so it's already deleted."
  comment_out_env
  exit 0
fi

# Try deleting with the key itself first, then with the admin token if one is set.
for AUTH in "$R2_READ_TOKEN" "${CLOUDFLARE_API_TOKEN:-}"; do
  [ -n "$AUTH" ] || continue
  ok=$(curl -s -X DELETE -H "Authorization: Bearer $AUTH" "$API/accounts/$ACCOUNT/tokens/$ID" |
    python3 -c 'import sys, json; print(json.load(sys.stdin).get("success"))')
  if [ "$ok" = True ]; then
    echo "Deleted the read-only R2 key ($ID)."
    comment_out_env
    exit 0
  fi
done

echo "Cloudflare refused to delete the key ($ID). Either:" >&2
echo "  - set CLOUDFLARE_API_TOKEN to a token with Account API Tokens: Edit and re-run, or" >&2
echo "  - delete it in the dashboard: R2 > Manage API tokens, then re-run to clean up .env." >&2
exit 1
