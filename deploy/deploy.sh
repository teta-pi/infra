#!/usr/bin/env bash
# Deploy TETA+PI to production server (164.90.235.66)
# Run from your local machine: ./deploy/deploy.sh
set -euo pipefail

SERVER="root@164.90.235.66"
REMOTE_DIR="/opt/tetapi"

echo "→ Syncing code to $SERVER:$REMOTE_DIR"
rsync -az --exclude='.git' --exclude='node_modules' --exclude='.next' \
  --exclude='__pycache__' --exclude='*.pyc' \
  . "$SERVER:$REMOTE_DIR/"

echo "→ Copying nginx configs"
ssh "$SERVER" "cp $REMOTE_DIR/deploy/nginx/*.conf /etc/nginx/sites-available/ && \
  for f in /etc/nginx/sites-available/tetapi.dev.conf \
            /etc/nginx/sites-available/app.tetapi.dev.conf \
            /etc/nginx/sites-available/api.tetapi.dev.conf \
            /etc/nginx/sites-available/mcp.tetapi.dev.conf; do \
    ln -sf \$f /etc/nginx/sites-enabled/\$(basename \$f); \
  done && \
  nginx -t && systemctl reload nginx"

echo "→ Building and starting services"
ssh "$SERVER" "cd $REMOTE_DIR && \
  docker compose -f docker-compose.prod.yml pull --quiet && \
  docker compose -f docker-compose.prod.yml up --build -d && \
  docker compose -f docker-compose.prod.yml ps"

echo "→ Copying landing static files"
ssh "$SERVER" "mkdir -p /var/www/tetapi/landing && \
  cp -r $REMOTE_DIR/landing/. /var/www/tetapi/landing/"

echo ""
echo "✓ Deploy complete"
echo "  https://tetapi.dev       → landing"
echo "  https://app.tetapi.dev   → web app"
echo "  https://api.tetapi.dev   → API"
echo "  https://mcp.tetapi.dev   → MCP"
echo ""
echo "  SSL: run certbot on the server if not already done:"
echo "  certbot --nginx -d tetapi.dev -d www.tetapi.dev -d app.tetapi.dev -d api.tetapi.dev -d mcp.tetapi.dev"
