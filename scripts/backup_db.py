# -*- coding: utf-8 -*-
"""Daily database backup — copies pos.db to data/backups/pos-YYYY-MM-DD.db.

Can be called via Windows Task Scheduler or manually.
Only touches SQLite. No PostgreSQL interaction.
"""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "pos.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def backup() -> str:
    if not DB_PATH.exists():
        return "No database to back up"

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"pos-{date.today().isoformat()}.db"
    shutil.copy2(str(DB_PATH), str(dest))
    return f"Backup created: {dest.name}"


if __name__ == "__main__":
    print(backup())
