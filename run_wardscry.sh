#!/usr/bin/env bash
set -euo pipefail

# WardScry one-click launcher (repo layout):
#   GUI:    ./main.py
#   Daemon: package module wardscry.daemon.wardscryd  (file: ./wardscry/daemon/wardscryd.py)
#
# Why module mode?
# Running a script by file path inside a package often breaks absolute imports like
# "from wardscry.db import ..." because Python sets sys.path[0] to wardscry/daemon/.
# Using "python -m wardscry.daemon.wardscryd" keeps the repo root on sys.path.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer project venv if it exists; otherwise fall back to system python3.
PY="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  PY="python3"
fi

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

# ---- GUI entrypoint (override with GUI_FILE=...) ----
GUI_FILE="${GUI_FILE:-$ROOT_DIR/main.py}"
if [ ! -f "$GUI_FILE" ]; then
  echo "[WardScry] ERROR: GUI file not found: $GUI_FILE" >&2
  exit 1
fi

# ---- Daemon entrypoint ----
# Default to module mode for this repo; override with:
#   DAEMON_MODE=file DAEMON_FILE=./some_script.py ./run_wardscry.sh
DAEMON_MODE="${DAEMON_MODE:-module}"

DAEMON_PID=""

cleanup() {
  if [ -n "${DAEMON_PID:-}" ] && kill -0 "$DAEMON_PID" 2>/dev/null; then
    echo "[WardScry] Stopping daemon (pid $DAEMON_PID)..."
    kill "$DAEMON_PID" 2>/dev/null || true
    wait "$DAEMON_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[WardScry] Using python: $PY"
echo "[WardScry] Logs: $LOG_DIR/daemon.log"

# Start daemon (background)
if [ "$DAEMON_MODE" = "module" ]; then
  # Ensure the module exists
  if [ -f "$ROOT_DIR/wardscry/daemon/wardscryd.py" ]; then
    echo "[WardScry] Starting daemon (module): python -m wardscry.daemon.wardscryd"
    (cd "$ROOT_DIR" && "$PY" -m wardscry.daemon.wardscryd >>"$LOG_DIR/daemon.log" 2>&1) &
    DAEMON_PID="$!"
  else
    echo "[WardScry] WARNING: daemon module file not found at wardscry/daemon/wardscryd.py. Starting GUI only." >&2
  fi
else
  DAEMON_FILE="${DAEMON_FILE:-$ROOT_DIR/wardscry/daemon/wardscryd.py}"
  if [ -f "$DAEMON_FILE" ]; then
    echo "[WardScry] Starting daemon (file): $DAEMON_FILE"
    (cd "$ROOT_DIR" && "$PY" "$DAEMON_FILE" >>"$LOG_DIR/daemon.log" 2>&1) &
    DAEMON_PID="$!"
  else
    echo "[WardScry] WARNING: daemon file not found: $DAEMON_FILE. Starting GUI only." >&2
  fi
fi

sleep 0.4

# Start GUI (foreground) WITHOUT exec, so traps still work and daemon is cleaned up.
echo "[WardScry] Starting GUI: $GUI_FILE"
(cd "$ROOT_DIR" && "$PY" "$GUI_FILE")
GUI_STATUS=$?

exit "$GUI_STATUS"
