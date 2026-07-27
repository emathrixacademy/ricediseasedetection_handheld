#!/usr/bin/env bash
# setup_db.sh — provision the PostgreSQL database for the rice scanner.
# Creates role `scanner_user`, database `ricescanner` (owned by scanner_user),
# and applies scripts/setup_db.sql. Idempotent-ish: safe to re-run.
#
# Usage:  ./scripts/setup_db.sh
# Requires: postgres client tools (psql, createdb) and privileges to create
#           roles/databases (run as the postgres superuser or with sudo -u postgres).

set -euo pipefail

DB_NAME="ricescanner"
DB_USER="scanner_user"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/setup_db.sql"

# Allow running as the postgres superuser. Prefer `sudo -u postgres` if present.
PSQL="psql"
CREATEDB="createdb"
if command -v sudo >/dev/null 2>&1 && id postgres >/dev/null 2>&1; then
    PSQL="sudo -u postgres psql"
    CREATEDB="sudo -u postgres createdb"
fi

echo "== Rice scanner DB setup =="

# 1. Prompt for the scanner_user password (hidden input).
read -r -s -p "Enter password for role '${DB_USER}': " DB_PASS
echo

# 2. Create the role if it does not already exist.
if $PSQL -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
    echo "Role '${DB_USER}' already exists — updating password."
    $PSQL -c "ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASS}';"
else
    echo "Creating role '${DB_USER}'."
    $PSQL -c "CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASS}';"
fi

# 3. Create the database owned by scanner_user if it does not exist.
if $PSQL -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    echo "Database '${DB_NAME}' already exists — skipping createdb."
else
    echo "Creating database '${DB_NAME}' owned by '${DB_USER}'."
    $CREATEDB -O "${DB_USER}" "${DB_NAME}"
fi

# 4. Apply the schema (CREATE TABLE IF NOT EXISTS makes this re-runnable).
echo "Applying schema from ${SQL_FILE}."
$PSQL -d "${DB_NAME}" -f "${SQL_FILE}"

echo "== Done. Database '${DB_NAME}' is ready. =="
