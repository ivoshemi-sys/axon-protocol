"""
Daily database backup.
- SQLite: copies oixa.db to backups/oixa_YYYY-MM-DD.db
- PostgreSQL: runs pg_dump to backups/oixa_YYYY-MM-DD.sql.gz
Keeps the last 30 backups and deletes older ones.
Runs at startup and then every 24 hours.
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH, DATABASE_URL, USE_POSTGRES

logger = logging.getLogger("oixa.backup")

BACKUP_INTERVAL_SECONDS = 24 * 3600  # 24 hours
MAX_BACKUPS = 30

BACKUP_DIR = Path(DB_PATH).parent / "backups" if not USE_POSTGRES else Path("./backups")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _backup_sqlite():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(DB_PATH)
    if not src.exists():
        logger.warning(f"[BACKUP] SQLite file not found: {src}")
        return
    dest = BACKUP_DIR / f"oixa_{_today()}.db"
    shutil.copy2(src, dest)
    logger.info(f"[BACKUP] SQLite backup → {dest} ({dest.stat().st_size // 1024} KB)")
    _prune_old_backups("*.db")


async def _backup_postgres():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"oixa_{_today()}.sql.gz"
    cmd = f'pg_dump "{DATABASE_URL}" | gzip > "{dest}"'
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error(f"[BACKUP] pg_dump failed: {stderr.decode()}")
        return
    logger.info(f"[BACKUP] PostgreSQL backup → {dest} ({dest.stat().st_size // 1024} KB)")
    _prune_old_backups("*.sql.gz")


def _prune_old_backups(pattern: str):
    backups = sorted(BACKUP_DIR.glob(pattern))
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        oldest.unlink()
        logger.info(f"[BACKUP] Pruned old backup: {oldest.name}")


async def run_backup():
    """Run one backup cycle now."""
    try:
        if USE_POSTGRES:
            await _backup_postgres()
        else:
            await _backup_sqlite()
    except Exception as exc:
        logger.error(f"[BACKUP] Backup failed: {exc}")


async def backup_loop():
    """Background task: backup every 24 hours, starting immediately."""
    logger.info("[BACKUP] Daily backup loop started")
    await run_backup()  # backup on startup
    while True:
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
        await run_backup()
