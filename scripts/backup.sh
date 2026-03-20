#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# OIXA Protocol — Manual database backup
# Usage: bash scripts/backup.sh [backup_dir]
# Default backup dir: server/backups/
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${1:-$ROOT_DIR/server/backups}"
DATE="$(date -u +%Y-%m-%d)"
SQLITE_DB="$ROOT_DIR/server/oixa.db"

mkdir -p "$BACKUP_DIR"

# Load .env if present
[ -f "$ROOT_DIR/.env" ] && source "$ROOT_DIR/.env" 2>/dev/null || true

if [ -n "${DATABASE_URL:-}" ] && [[ "$DATABASE_URL" == postgresql* ]]; then
    echo "▶ Backing up PostgreSQL → $BACKUP_DIR/oixa_$DATE.sql.gz"
    pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/oixa_$DATE.sql.gz"
    SIZE=$(du -sh "$BACKUP_DIR/oixa_$DATE.sql.gz" | cut -f1)
    echo "  ✅ PostgreSQL backup complete ($SIZE)"
elif [ -f "$SQLITE_DB" ]; then
    echo "▶ Backing up SQLite → $BACKUP_DIR/oixa_$DATE.db"
    cp "$SQLITE_DB" "$BACKUP_DIR/oixa_$DATE.db"
    SIZE=$(du -sh "$BACKUP_DIR/oixa_$DATE.db" | cut -f1)
    echo "  ✅ SQLite backup complete ($SIZE)"
else
    echo "❌ No database found (checked $SQLITE_DB)"
    exit 1
fi

# Prune backups older than 30 days
echo "▶ Pruning backups older than 30 days..."
find "$BACKUP_DIR" -name "oixa_*.db" -mtime +30 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "oixa_*.sql.gz" -mtime +30 -delete 2>/dev/null || true
echo "  ✅ Pruned"

echo ""
echo "Backups in $BACKUP_DIR:"
ls -lh "$BACKUP_DIR" 2>/dev/null || echo "  (empty)"
