#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
extras=(--extra dev)
if [ -d .lab ]; then extras+=(--extra lab); fi
uv sync --project backend "${extras[@]}"
npm --prefix frontend ci
npm --prefix frontend run build
if [ "${1:-}" = "--demo" ]; then
  backend/.venv/bin/python -m finops_agent.demo
fi
exec backend/.venv/bin/uvicorn finops_agent.api.server:app --host 127.0.0.1 --port "${PORT:-8000}"
