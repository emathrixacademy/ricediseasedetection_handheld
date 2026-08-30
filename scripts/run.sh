#!/usr/bin/env bash
# run.sh — launch the rice scanner application on the Raspberry Pi 5.
# Activates the virtualenv, starts the Flask monitoring dashboard in the
# background, then runs the main scanner loop in the foreground.
# On exit (Ctrl-C or main exit) the dashboard is cleaned up.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PROJECT_ROOT}/venv"
DASHBOARD_PID=""

# --- cleanup trap -----------------------------------------------------------
cleanup() {
    echo
    echo "Shutting down..."
    if [[ -n "${DASHBOARD_PID}" ]] && kill -0 "${DASHBOARD_PID}" 2>/dev/null; then
        echo "Stopping dashboard (pid ${DASHBOARD_PID})."
        kill "${DASHBOARD_PID}" 2>/dev/null || true
        wait "${DASHBOARD_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# --- activate virtualenv ----------------------------------------------------
if [[ -f "${VENV}/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${VENV}/bin/activate"
else
    echo "WARNING: virtualenv not found at ${VENV}; using system Python." >&2
fi

cd "${PROJECT_ROOT}"

# --- start monitoring dashboard (background) --------------------------------
# Both must be launched with -m from the project root. Running them as file
# paths (python pi5/main.py) puts pi5/ on sys.path instead of the root, so the
# `pi5.*` package imports fail -- main.py then silently disables every
# subsystem and reports "unknown" instead of erroring.
echo "Starting monitoring dashboard..."
python -m pi5.monitor.dashboard &
DASHBOARD_PID=$!
echo "Dashboard running (pid ${DASHBOARD_PID})."

# --- start main scanner loop (foreground) -----------------------------------
echo "Starting main scanner..."
python -m pi5.main

# When main.py exits, the EXIT trap cleans up the dashboard.
