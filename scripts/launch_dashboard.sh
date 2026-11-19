#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${CTE442_PYTHON:-}" ]]; then
  PYTHON_BIN="$CTE442_PYTHON"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
else
  PYTHON_BIN="python3"
fi
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_BIN" -m cte442_asr.cli dashboard --host 127.0.0.1 --port "${CTE442_DASHBOARD_PORT:-8765}"

