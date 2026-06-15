#!/usr/bin/env bash
set -euo pipefail

docker compose -f deploy/docker-compose.dev.yml up -d
cd backend
uv run uvicorn app.main:app --reload --port 8002
