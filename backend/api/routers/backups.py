"""Database backup endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..services.backup_service import BackupService

router = APIRouter(prefix="/database", tags=["Backups"])


@router.post("/backup")
async def create_backup():
    """Create a manual database backup."""
    backup_path = BackupService.create_backup()
    if backup_path:
        from pathlib import Path
        return {
            "success": True,
            "message": "Backup created successfully",
            "path": Path(backup_path).name
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to create backup")


@router.get("/backups")
async def list_backups():
    """List all available database backups."""
    backups = BackupService.list_backups()
    return {
        "count": len(backups),
        "backups": backups
    }


@router.get("/download-backup/{filename}")
async def download_backup(filename: str):
    """Download a specific backup file."""
    backup_path = BackupService.get_backup_path(filename)

    if backup_path is None:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")

    return FileResponse(
        path=backup_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@router.delete("/backup/{filename}")
async def delete_backup(filename: str):
    """Delete a specific backup file."""
    if BackupService.delete_backup(filename):
        return {"success": True, "message": f"Backup {filename} deleted"}
    else:
        raise HTTPException(status_code=404, detail="Backup not found or could not be deleted")
