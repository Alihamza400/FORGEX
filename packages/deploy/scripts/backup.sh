#!/usr/bin/env bash
# forge-backup — backup all data services
set -euo pipefail

BACKUP_DIR="${FORGE_BACKUP_DIR:-/var/lib/forge/backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/${DATE}"
RETENTION_DAYS="${FORGE_BACKUP_RETENTION_DAYS:-7}"

mkdir -p "${BACKUP_PATH}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ── Postgres ──────────────────────────────────────────────────────────
backup_postgres() {
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

    log "Backing up Postgres: ${db}@${host}:${port}"
    PGPASSWORD="${pass}" pg_dump \
        -h "${host}" -p "${port}" -U "${user}" -d "${db}" \
        --format=custom --compress=9 \
        -f "${BACKUP_PATH}/postgres.dump" \
        --no-owner --no-acl 2>/dev/null
    log "  -> postgres.dump ($(du -h "${BACKUP_PATH}/postgres.dump" | cut -f1))"
}

# ── Qdrant ────────────────────────────────────────────────────────────
backup_qdrant() {
    local qdrant_url="${QDRANT_URL:-http://localhost:6333}"
    log "Backing up Qdrant collections list"
    local collections
    collections=$(curl -sf "${qdrant_url}/collections" 2>/dev/null | python3 -c "import sys,json; [print(c['name']) for c in json.load(sys.stdin).get('result',{}).get('collections',[])]" 2>/dev/null || echo "")

    if [ -z "$collections" ]; then
        log "  SKIP: No Qdrant collections found or not reachable"
        return
    fi

    mkdir -p "${BACKUP_PATH}/qdrant"
    echo "$collections" | while IFS= read -r col; do
        [ -z "$col" ] && continue
        log "  Snapshotting collection: ${col}"
        local snap_resp
        snap_resp=$(curl -sf -X POST "${qdrant_url}/collections/${col}/snapshots" 2>/dev/null || echo "")
        local snap_name
        snap_name=$(echo "$snap_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('name',''))" 2>/dev/null || echo "")
        if [ -n "$snap_name" ]; then
            curl -sf -o "${BACKUP_PATH}/qdrant/${col}.snapshot" \
                "${qdrant_url}/collections/${col}/snapshots/${snap_name}" 2>/dev/null
            log "    -> qdrant/${col}.snapshot"
            curl -sf -X DELETE "${qdrant_url}/collections/${col}/snapshots/${snap_name}" >/dev/null 2>&1 || true
        fi
    done
}

# ── MinIO ─────────────────────────────────────────────────────────────
backup_minio() {
    local endpoint="${MINIO_ENDPOINT:-localhost:9000}"
    local access_key="${MINIO_ACCESS_KEY:-}"
    local secret_key="${MINIO_SECRET_KEY:-}"
    local bucket="${MINIO_DEFAULT_BUCKET:-forge}"

    if [ -z "$access_key" ] || [ -z "$secret_key" ]; then
        log "SKIP: MINIO_ACCESS_KEY or MINIO_SECRET_KEY not set"
        return
    fi

    if ! command -v mc &>/dev/null; then
        log "SKIP: mc (MinIO client) not installed"
        return
    fi

    log "Backing up MinIO bucket: ${bucket}"
    mc alias set forge-minio "http://${endpoint}" "${access_key}" "${secret_key}" 2>/dev/null
    mc mirror forge-minio/"${bucket}" "${BACKUP_PATH}/minio/" 2>/dev/null
    log "  -> minio/ ($(du -sh "${BACKUP_PATH}/minio" | cut -f1))"
}

# ── Main ──────────────────────────────────────────────────────────────
log "Starting backup to ${BACKUP_PATH}"
echo "────────────────────────────────────────"

backup_postgres
echo ""
backup_qdrant
echo ""
backup_minio
echo ""
log "Backup complete: ${BACKUP_PATH}"
du -sh "${BACKUP_PATH}"

# ── Retention ─────────────────────────────────────────────────────────
if [ "${RETENTION_DAYS}" -gt 0 ]; then
    log "Cleaning backups older than ${RETENTION_DAYS} days"
    find "${BACKUP_DIR}" -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} \; 2>/dev/null || true
fi
