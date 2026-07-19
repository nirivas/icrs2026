#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v npx >/dev/null; then
  echo "Need Node/npx to run wrangler." >&2
  exit 1
fi

echo "Creating KV namespace (if needed)…"
OUT="$(npx wrangler kv namespace create SYNC 2>&1 || true)"
echo "$OUT"
ID="$(echo "$OUT" | sed -n 's/.*id = "\([^"]*\)".*/\1/p' | head -1)"
if [[ -n "$ID" ]]; then
  sed -i '' "s/id = \"REPLACE_AFTER_KV_CREATE\"/id = \"$ID\"/" wrangler.toml
  echo "Updated wrangler.toml with namespace id $ID"
fi

echo "Deploying worker…"
npx wrangler deploy

echo ""
echo "Set assets/sync-config.js to:"
echo "  window.ICRS_SYNC_URL = 'https://icrs2026-sync.<your-subdomain>.workers.dev';"
echo "(wrangler prints the exact URL above)"
