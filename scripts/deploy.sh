#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/calibration-bot}"

cd "$APP_DIR"

git fetch origin main
git reset --hard origin/main

if grep -q 'OPENROUTER_MODEL=google/gemini-2.0-flash-001' .env 2>/dev/null; then
  sed -i 's/OPENROUTER_MODEL=google\/gemini-2.0-flash-001/OPENROUTER_MODEL=google\/gemini-2.5-flash-lite/' .env
fi

docker compose down --remove-orphans
docker compose up -d --build

docker compose ps
docker compose logs --tail=20 bot
