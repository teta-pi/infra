#!/usr/bin/env bash
# Deploy TETA+PI to production server (164.90.235.66)
# Run from repo root: ./deploy/deploy.sh
set -euo pipefail

SERVER="root@164.90.235.66"
REMOTE_DIR="/opt/tetapi"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== TETA+PI Deploy → $SERVER ==="

# ── 1. Sync API code ──────────────────────────────────────────────────────────
echo "→ Syncing API..."
rsync -az --delete \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  --exclude='certs/*.key.pem' \
  "$REPO_ROOT/api/" "$SERVER:$REMOTE_DIR/api/"

# Sync public certs only (never sync private keys)
rsync -az \
  "$REPO_ROOT/api/certs/root_ca.cert.pem" \
  "$REPO_ROOT/api/certs/signing.cert.pem" \
  "$REPO_ROOT/api/certs/chain.cert.pem" \
  "$SERVER:$REMOTE_DIR/api/certs/"

# ── 2. Build web standalone locally ──────────────────────────────────────────
echo "→ Building Next.js (standalone)..."
cd "$REPO_ROOT/web"
NEXT_PUBLIC_API_URL="https://api.tetapi.dev" npx next build --no-lint 2>&1 | tail -8

# ── 3. Sync Next.js output ───────────────────────────────────────────────────
echo "→ Syncing Next.js standalone..."
rsync -az --delete --exclude='cache' \
  "$REPO_ROOT/web/.next/standalone/" "$SERVER:$REMOTE_DIR/web/"

rsync -az --delete \
  "$REPO_ROOT/web/.next/static/" "$SERVER:$REMOTE_DIR/web/.next/static/"

rsync -az --delete \
  "$REPO_ROOT/web/public/" "$SERVER:$REMOTE_DIR/web/public/"

# ── 4. Post-build patches (Next.js 15 standalone quirks) ─────────────────────
echo "→ Applying Next.js standalone patches..."
ssh "$SERVER" bash <<'REMOTE'
set -e
NEXT="$HOME/../opt/tetapi/web/.next"

# Numeric chunk files must be in .next/server/ root (Next.js 15 loads from there)
for chunk in "$NEXT/server/chunks/"[0-9]*.js; do
  [ -f "$chunk" ] && cp -n "$chunk" "$NEXT/server/$(basename $chunk)" 2>/dev/null || true
done

# pages.runtime.dev.js symlink (standalone only ships prod variant)
MODS="$NEXT/../node_modules/next/dist/compiled/next-server"
if [ -d "$MODS" ] && [ ! -f "$MODS/pages.runtime.dev.js" ] && [ -f "$MODS/pages.runtime.prod.js" ]; then
  ln -sf pages.runtime.prod.js "$MODS/pages.runtime.dev.js"
fi

# Fix doubled BUILD_ID (standalone sometimes concatenates it)
if [ -f "$NEXT/BUILD_ID" ]; then
  BUILD_ID=$(head -c 40 "$NEXT/BUILD_ID" | tr -d '\n')
  printf '%s' "$BUILD_ID" > "$NEXT/BUILD_ID"
fi

# Patch app-paths-manifest.json (standalone omits /claim + /.well-known routes)
cat > "$NEXT/server/app-paths-manifest.json" <<'JSON'
{
  "/page": "app/page.js",
  "/profile/page": "app/profile/page.js",
  "/claim/page": "app/claim/page.js",
  "/.well-known/agent.json/route": "app/.well-known/agent.json/route.js",
  "/_not-found/page": "app/_not-found/page.js"
}
JSON
echo "  patches applied"
REMOTE

# ── 5. Sync landing ──────────────────────────────────────────────────────────
echo "→ Syncing landing..."
rsync -az --delete \
  --exclude='.git' \
  "$REPO_ROOT/landing/" "$SERVER:/var/www/tetapi/landing/"

# ── 6. DB migrations + restart services ──────────────────────────────────────
echo "→ Running migrations + restarting services..."
ssh "$SERVER" bash <<'REMOTE'
set -e
cd /opt/tetapi/api
source .venv/bin/activate 2>/dev/null || pip3 install -e . -q

echo "  running alembic upgrade head..."
alembic upgrade head 2>&1 | tail -5

echo "  restarting tetapi-api..."
systemctl restart tetapi-api
sleep 3
systemctl is-active --quiet tetapi-api && echo "  ✓ API  up" || { echo "  ✗ API  failed"; journalctl -u tetapi-api -n 20 --no-pager; }

echo "  restarting tetapi-web..."
systemctl restart tetapi-web
sleep 3
systemctl is-active --quiet tetapi-web && echo "  ✓ Web  up" || { echo "  ✗ Web  failed"; journalctl -u tetapi-web -n 20 --no-pager; }
REMOTE

echo ""
echo "=== Deploy complete ==="
echo "  https://app.tetapi.dev/claim  →  onboarding"
echo "  https://app.tetapi.dev/profile →  profile"
echo "  https://api.tetapi.dev/docs    →  API docs"
echo ""
echo "  ⚠  Private keys NOT synced — copy signing.key.pem manually if new server"
echo "     scp api/certs/signing.key.pem $SERVER:$REMOTE_DIR/api/certs/"
echo "     Then add C2PA_SIGNING_KEY_PEM to /opt/tetapi/api/.env"
