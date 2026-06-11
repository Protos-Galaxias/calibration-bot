#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/calibration-bot}"

cd "$APP_DIR"

git fetch origin main
git reset --hard origin/main

if grep -q 'OPENROUTER_MODEL=google/gemini-2.0-flash-001' .env 2>/dev/null; then
  sed -i 's/OPENROUTER_MODEL=google\/gemini-2.0-flash-001/OPENROUTER_MODEL=google\/gemini-2.5-flash-lite/' .env
fi

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build first — on failure bring back the previous image so the bot stays up.
if ! docker compose build; then
  echo "Build failed — restarting with existing image"
  docker compose up -d --remove-orphans
  docker compose ps
  exit 1
fi

# Never pass -v: bot-data volume holds calibration.db
docker compose up -d --remove-orphans

docker compose ps
docker compose logs --tail=20 bot
