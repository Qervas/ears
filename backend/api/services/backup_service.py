"""Database backup service."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH
from ..dependencies import BACKUP_DIR


class BackupService:
    """Service for database backup operations."""

    @staticmethod
    def create_backup() -> Optional[str]:
        """Create a timestamped backup of the database."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"transcripts_backup_{timestamp}.db"

        try:
            shutil.copy2(DATABASE_PATH, backup_path)
            print(f"✓ Database backup created: {backup_path.name}")

            # Keep only last 10 backups
            backups = sorted(
                BACKUP_DIR.glob("transcripts_backup_*.db"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for old_backup in backups[10:]:
                old_backup.unlink()
                print(f"  Removed old backup: {old_backup.name}")

            return str(backup_path)
        except Exception as e:
            print(f"✗ Failed to create backup: {e}")
            return None

    @staticmethod
    def get_latest_backup() -> Optional[Path]:
        """Get the most recent backup file."""
        backups = sorted(
            BACKUP_DIR.glob("transcripts_backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return backups[0] if backups else None

    @staticmethod
    def list_backups() -> list[dict]:
        """List all available backups with metadata."""
        backups = sorted(
            BACKUP_DIR.glob("transcripts_backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        backup_list = []
        for backup in backups:
            stat = backup.stat()
            backup_list.append({
                "filename": backup.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

        return backup_list

    @staticmethod
    def get_backup_path(filename: str) -> Optional[Path]:
        """Get path to a specific backup file (with security validation)."""
        # Prevent directory traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            return None

        backup_path = BACKUP_DIR / filename
        if backup_path.exists():
            return backup_path
        return None
