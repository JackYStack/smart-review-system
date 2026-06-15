#!/usr/bin/env bash
set -euo pipefail

cd backend
uv run ruff check app tests
uv run mypy app
uv run pytest tests -v
