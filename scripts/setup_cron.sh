#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# OIXA Protocol — Set up cron jobs on the VPS
# Run this ONCE after deploy: bash scripts/setup_cron.sh
# Or SSH and run: bash /opt/oixa-protocol/scripts/setup_cron.sh
# ─────────────────────────────────────────────────────────────────────────────

DEPLOY_DIR="${DEPLOY_DIR:-/opt/oixa-protocol}"

# Daily backup at 3:00 AM UTC
BACKUP_CRON="0 3 * * * $DEPLOY_DIR/scripts/backup.sh >> $DEPLOY_DIR/logs/backup.log 2>&1"

# Add to crontab only if not already present
(crontab -l 2>/dev/null | grep -v "oixa-protocol/scripts/backup"; echo "$BACKUP_CRON") | crontab -

echo "✅ Cron jobs configured:"
crontab -l | grep oixa
echo ""
echo "Backup runs daily at 3:00 AM UTC → $DEPLOY_DIR/logs/backup.log"
