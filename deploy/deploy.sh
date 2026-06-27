#!/usr/bin/env bash
# Deploy TETA+PI to production server (164.90.235.66)
# Run from repo root: ./deploy/deploy.sh
# Requires: sshpass (brew install sshpass) + TETAPI_SSH_PASS env var
#   export TETAPI_SSH_PASS='<server-root-password>'
#   ./deploy/deploy.sh
set -euo pipefail

SERVER="root@164.90.235.66"
REMOTE_DIR="/opt/tetapi"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS="${TETAPI_SSH_PASS:-}"

SSH_OPTS="-o StrictHostKeyChecking=no"
if [ -n "$PASS" ]; then
  RSYNC_SHELL="sshpass -p '$PASS' ssh $SSH_OPTS"
  alias _ssh="sshpass -p '$PASS' ssh $SSH_OPTS $SERVER"
  _ssh() { sshpass -p "$PASS" ssh $SSH_OPTS "$SERVER" "$@"; }
  _rsync() { sshpass -p "$PASS" rsync -az -e "ssh $SSH_OPTS" "$@"; }
else
  _ssh() { ssh $SSH_OPTS "$SERVER" "$@"; }
  _rsync() { rsync -az -e "ssh $SSH_OPTS" "$@"; }
fi

echo "=== TETA+PI Deploy → $SERVER ==="

# ── 1. Sync API code ──────────────────────────────────────────────────────────
echo "→ Syncing API..."
_rsync --delete \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  --exclude='certs/*.key.pem' --exclude='.env' \
  "$REPO_ROOT/api/" "$SERVER:$REMOTE_DIR/api/"

# Public certs only — private keys never leave local machine
_rsync \
  "$REPO_ROOT/api/certs/root_ca.cert.pem" \
  "$REPO_ROOT/api/certs/signing.cert.pem" \
  "$REPO_ROOT/api/certs/chain.cert.pem" \
  "$SERVER:$REMOTE_DIR/api/certs/"

# ── 2. Build Next.js standalone ──────────────────────────────────────────────
echo "→ Building Next.js (standalone)..."
cd "$REPO_ROOT/web"
NEXT_PUBLIC_API_URL="https://api.tetapi.dev" npx next build --no-lint 2>&1 | tail -8

# ── 3. Sync Next.js output ───────────────────────────────────────────────────
# Standalone structure: .next/standalone/ contains node_modules/ + web/ subdir
# On server: /opt/tetapi/web/ maps to standalone root
#            /opt/tetapi/web/web/ is where server.js + .next/ live

echo "→ Syncing Next.js standalone..."
_rsync --delete --exclude='cache' \
  "$REPO_ROOT/web/.next/standalone/" "$SERVER:$REMOTE_DIR/web/"

# Static assets live inside the nested web/ subdirectory
_ssh "mkdir -p $REMOTE_DIR/web/web/.next/static"
_rsync --delete \
  "$REPO_ROOT/web/.next/static/" "$SERVER:$REMOTE_DIR/web/web/.next/static/"

# Server build artifacts (app/ pages, chunks, manifests)
_rsync \
  "$REPO_ROOT/web/.next/server/" "$SERVER:$REMOTE_DIR/web/web/.next/server/"

# ── 4. Post-build patches (Next.js 15 standalone quirks) ─────────────────────
echo "→ Applying Next.js standalone patches..."
_ssh bash << 'REMOTE'
set -e
NEXT="/opt/tetapi/web/web/.next"

# Numeric chunk files to server root (Next.js 15 resolves them from there)
for chunk in "$NEXT/server/chunks/"[0-9]*.js; do
  [ -f "$chunk" ] && cp -n "$chunk" "$NEXT/server/$(basename $chunk)" 2>/dev/null || true
done

# Fix doubled BUILD_ID
BUILD_ID=$(head -c 40 "$NEXT/BUILD_ID" | tr -d '\n')
printf '%s' "$BUILD_ID" > "$NEXT/BUILD_ID"
echo "  BUILD_ID: $BUILD_ID"

# Patch app-paths-manifest.json (standalone sometimes misses /claim, /.well-known)
cat > "$NEXT/server/app-paths-manifest.json" << 'JSON'
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
if [ -d "$REPO_ROOT/landing" ]; then
  echo "→ Syncing landing..."
  _ssh "mkdir -p /var/www/tetapi/landing"
  _rsync --delete --exclude='.git' \
    "$REPO_ROOT/landing/" "$SERVER:/var/www/tetapi/landing/"
fi

# ── 6. DB migrations + restart services ──────────────────────────────────────
echo "→ Running migrations + restarting services..."
_ssh bash << 'REMOTE'
set -e
cd /opt/tetapi/api
source /opt/tetapi/venv/bin/activate

echo "  alembic upgrade head..."
alembic upgrade head 2>&1 | tail -5

echo "  restarting tetapi-api..."
systemctl restart tetapi-api
sleep 4
systemctl is-active --quiet tetapi-api && echo "  ✓ API  up" || { echo "  ✗ API  failed"; journalctl -u tetapi-api -n 30 --no-pager; exit 1; }

echo "  restarting tetapi-web..."
systemctl restart tetapi-web
sleep 4
systemctl is-active --quiet tetapi-web && echo "  ✓ Web  up" || { echo "  ✗ Web  failed"; journalctl -u tetapi-web -n 30 --no-pager; exit 1; }
REMOTE

echo ""
echo "=== Deploy complete ==="
echo "  https://app.tetapi.dev/claim   →  onboarding"
echo "  https://app.tetapi.dev/profile →  profile"
echo "  https://api.tetapi.dev/docs    →  API docs"
echo ""
echo "  ⚠  Private signing key NOT synced — if new server:"
echo "     scp api/certs/signing.key.pem root@164.90.235.66:/opt/tetapi/api/certs/"
echo "     Then set C2PA_SIGNING_KEY_PEM in /opt/tetapi/api/.env"
