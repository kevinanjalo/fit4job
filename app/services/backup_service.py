"""Backup and maintenance utilities for the admin dashboard."""
import shutil
import time
from pathlib import Path

BACKUP_DIR = Path("backups")


def create_backup() -> str:
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"fit4job_data_{stamp}"
    shutil.make_archive(str(target), "zip", "data")
    return f"{target}.zip"


def list_backups() -> list:
    if not BACKUP_DIR.exists():
        return []
    return sorted(p.name for p in BACKUP_DIR.glob("*.zip"))
