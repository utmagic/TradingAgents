#!/usr/bin/env bash
set -euo pipefail

pkill -f "uvicorn web.backend.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true

echo "Stopped backend/frontend if running."
