#!/usr/bin/env bash
# =============================================================================
# SolarGuard -- Safe Live SQLite Backup Script
# Performs online, zero-downtime atomic backup using SQLite's .backup API.
# Safe for concurrent reads and writes during active demonstrations.
# =============================================================================

set -o errexit
set -o nounset

APP_DIR="/var/www/solarguard"
BACKUP_DIR="${APP_DIR}/backups"
DB_FILE="${APP_DIR}/db.sqlite3"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/solarguard_${TIMESTAMP}.sqlite3"

mkdir -p "${BACKUP_DIR}"

if [ ! -f "${DB_FILE}" ]; then
    echo "[ERROR] Database file not found at ${DB_FILE}"
    exit 1
fi

echo "========================================================================"
echo " SolarGuard -- SQLite Live Backup"
echo "========================================================================"
echo "Source DB:   ${DB_FILE}"
echo "Destination: ${BACKUP_FILE}"

# 1. Perform atomic online backup using SQLite's internal backup API
sqlite3 "${DB_FILE}" ".backup '${BACKUP_FILE}'"

# 2. Verify integrity of the backup copy
INTEGRITY=$(sqlite3 "${BACKUP_FILE}" "PRAGMA integrity_check;")
if [ "${INTEGRITY}" != "ok" ]; then
    echo "[FAIL] Backup integrity check failed: ${INTEGRITY}"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[PASS] Backup created and verified successfully (${BACKUP_SIZE})."

# 3. Retain last 7 days of backups, delete older copies
echo "Pruning backups older than 7 days..."
find "${BACKUP_DIR}" -name "solarguard_*.sqlite3" -type f -mtime +7 -delete

echo "Current backups in ${BACKUP_DIR}:"
ls -lh "${BACKUP_DIR}"/solarguard_*.sqlite3 | awk '{print $9, "(" $5 ")"}'
echo "========================================================================"
