#!/usr/bin/env bash
# forge-restore — restore data services from a backup
set -euo pipefail

usage() {
    echo "Usage: $0 <backup-path>"
    echo "  Restores Postgres, Qdrant, and MinIO from a forge-backup snapshot"
    exit 1
}

BACKUP_PATH="${1:-}"
[ -z "$BACKUP_PATH" ] && usage
[ ! -d "$BACKUP_PATH" ] && echo "ERROR: Backup path not found: ${BACKUP_PATH}" && exit 1

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ── Postgres ──────────────────────────────────────────────────────────
restore_postgres() {
    local dump="${BACKUP_PATH}/postgres.dump"
    [ ! -f "$dump" ] && log "SKIP: No postgres dump found" && return

    local db_url="${DATABASE_URL:-}"
    if [ -z "$db_url" ]; then
        log "SKIP: DATABASE_URL not set"
        return
    fi

    local host port user pass db
    host=$(echo "$db_url" | sed -n 's/.*@\([^:]*\).*/\1/p')
    port=$(echo "$db_url" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    user=$(echo "$db_url" | sed -n 's/.*:\/\/\([^:]*\).*/\1/p')
    pass=$(echo "$db_url" | sed -n 's/.*:\/\/[^:]*:\([^@]*\).*/\1/p')
    db=$(echo "$db_url" | sed -n 's/.*\/\([^?]*\).*/\1/p')

    log "Restoring Postgres: ${db}"
    PGPASSWORD="${pass}" pg_restore \
        -h "${host}" -p "${port}" -U "${user}" -d "${db}" \
        --clean --if-exists --no-owner --no-acl \
        "${dump}" 2>/dev/null
    log "  -> Postgres restored"
}

# ── Qdrant ────────────────────────────────────────────────────────────
restore_qdrant() {
    local snap_dir="${BACKUP_PATH}/qdrant"
    [ ! -d "$snap_dir" ] && log "SKIP: No Qdrant snapshots found" && return

    local qdrant_url="${QDRANT_URL:-http://localhost:6333}"

    for snap in "${snap_dir}"/*.snapshot; do
        [ ! -f "$snap" ] && continue
        local col_name
        col_name=$(basename "$snap" .snapshot)
        log "Restoring Qdrant collection: ${col_name}"

        curl -sf -X POST "${qdrant_url}/collections/${col_name}/snapshots/upload" \
            -F "snapshot=@${snap}" >/dev/null 2>&1 || log "  WARN: Failed to restore ${col_name}"
        log "  -> ${col_name} restored"
    done
}

# ── MinIO ─────────────────────────────────────────────────────────────
restore_minio() {
    local minio_dir="${BACKUP_PATH}/minio"
    [ ! -d "$minio_dir" ] && log "SKIP: No MinIO backup found" && return

    local endpoint="${MINIO_ENDPOINT:-localhost:9000}"
    local access_key="${MINIO_ACCESS_KEY:-}"
    local secret_key="${MINIO_SECRET_KEY:-}"
    local bucket="${MINIO_DEFAULT_BUCKET:-forge}"

    if ! command -v mc &>/dev/null; then
        log "SKIP: mc (MinIO client) not installed"
        return
    fi

    log "Restoring MinIO bucket: ${bucket}"
    mc alias set forge-minio "http://${endpoint}" "${access_key}" "${secret_key}" 2>/dev/null
    mc mirror "${minio_dir}" forge-minio/"${bucket}" 2>/dev/null
    log "  -> MinIO restored"
}

# ── Main ──────────────────────────────────────────────────────────────
log "Starting restore from ${BACKUP_PATH}"
echo "────────────────────────────────"
restore_postgres
echo ""
restore_qdrant
echo ""
restore_minio
echo ""
log "Restore complete from ${BACKUP_PATH}"
