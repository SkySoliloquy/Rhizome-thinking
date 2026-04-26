"""Backup management API routes."""

import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field

from rhizome.core.backup_manager import BackupManager
from rhizome.api.dependencies import get_node_store
from rhizome.core.node_store import NodeStore

logger = logging.getLogger(__name__)

router = APIRouter()


class BackupCreateResponse(BaseModel):
    """Response after creating a backup."""
    success: bool
    message: str
    backup_name: str
    node_count: int
    size_mb: float


class BackupListResponse(BaseModel):
    """Response for listing backups."""
    backups: list[dict]
    total: int


class BackupRestoreRequest(BaseModel):
    """Request to restore from a backup."""
    confirm: bool = Field(default=False, description="是否清空现有数据后恢复")


class BackupRestoreResponse(BaseModel):
    """Response after restoring a backup."""
    success: bool
    message: str
    restored_nodes: int
    backup_date: Optional[str] = None


class BackupInfoResponse(BaseModel):
    """Response for backup information."""
    name: str
    created_at: str
    node_count: int
    backup_type: str
    version: str
    size_mb: float
    includes_vectors: bool


def get_backup_manager() -> BackupManager:
    """Get backup manager instance."""
    return BackupManager()


@router.get("/backups", response_model=BackupListResponse)
async def list_backups():
    """List all available backups."""
    try:
        manager = get_backup_manager()
        backups = manager.list_backups()
        return BackupListResponse(backups=backups, total=len(backups))
    except Exception as e:
        logger.exception("Failed to list backups")
        raise HTTPException(status_code=500, detail=f"获取备份列表失败: {str(e)}")


@router.post("/backups", response_model=BackupCreateResponse)
async def create_backup(
    name: Optional[str] = Query(default=None, description="备份名称（可选）")
):
    """Create a new backup."""
    try:
        manager = get_backup_manager()
        backup_path = manager.backup(output_path=name)

        # Get info about the created backup
        info = manager.get_backup_info(str(backup_path))

        return BackupCreateResponse(
            success=True,
            message="备份创建成功",
            backup_name=info["name"],
            node_count=info["node_count"],
            size_mb=info["size_mb"]
        )
    except Exception as e:
        logger.exception("Failed to create backup")
        raise HTTPException(status_code=500, detail=f"创建备份失败: {str(e)}")


@router.get("/backups/{backup_name}", response_model=BackupInfoResponse)
async def get_backup_info(backup_name: str):
    """Get detailed information about a backup."""
    try:
        manager = get_backup_manager()
        info = manager.get_backup_info(str(manager.backups_dir / backup_name))

        return BackupInfoResponse(
            name=info["name"],
            created_at=info["created_at"],
            node_count=info["node_count"],
            backup_type=info["backup_type"],
            version=info["version"],
            size_mb=info["size_mb"],
            includes_vectors=info["includes_vectors"]
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="备份文件未找到")
    except Exception as e:
        logger.exception("Failed to get backup info")
        raise HTTPException(status_code=500, detail=f"获取备份信息失败: {str(e)}")


@router.post("/backups/{backup_name}/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    backup_name: str,
    request: BackupRestoreRequest,
    node_store: NodeStore = Depends(get_node_store)
):
    """Restore from a backup."""
    try:
        manager = get_backup_manager()
        backup_path = manager.backups_dir / backup_name

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="备份文件未找到")

        result = manager.restore(str(backup_path), confirm=request.confirm)

        # Reload node store after restore
        node_store.reload()

        return BackupRestoreResponse(
            success=result["success"],
            message=result["message"],
            restored_nodes=result["restored_nodes"],
            backup_date=result.get("backup_date")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to restore backup")
        raise HTTPException(status_code=500, detail=f"恢复备份失败: {str(e)}")


@router.delete("/backups/{backup_name}")
async def delete_backup(backup_name: str):
    """Delete a backup file."""
    try:
        manager = get_backup_manager()
        success = manager.delete_backup(backup_name)

        if not success:
            raise HTTPException(status_code=404, detail="备份文件未找到")

        return {"message": "备份已删除", "backup_name": backup_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete backup")
        raise HTTPException(status_code=500, detail=f"删除备份失败: {str(e)}")


@router.get("/backups/{backup_name}/download")
async def download_backup(backup_name: str):
    """Download a backup file."""
    from fastapi.responses import FileResponse

    try:
        manager = get_backup_manager()
        backup_path = manager.backups_dir / backup_name

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="备份文件未找到")

        return FileResponse(
            path=str(backup_path),
            filename=backup_name,
            media_type="application/zip"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to download backup")
        raise HTTPException(status_code=500, detail=f"下载备份失败: {str(e)}")


@router.post("/backups/upload")
async def upload_backup(file: UploadFile = File(...)):
    """Upload and import a backup file."""
    import zipfile
    import json
    from datetime import datetime

    try:
        manager = get_backup_manager()

        # Validate file type
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="只支持 .zip 格式的备份文件")

        # Generate safe filename
        safe_filename = Path(file.filename).name
        backup_path = manager.backups_dir / safe_filename

        # If file exists, add number suffix
        counter = 1
        original_path = backup_path
        while backup_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            backup_path = manager.backups_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        # Save uploaded file
        with open(backup_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        # Validate the backup and update created_at to current time
        try:
            # Read and update manifest
            with zipfile.ZipFile(backup_path, 'r') as zf:
                manifest_content = zf.read('backup_manifest.json')
                manifest = json.loads(manifest_content)

            # Update created_at to current time
            manifest['created_at'] = datetime.now().isoformat()

            # Write updated manifest back to zip
            with zipfile.ZipFile(backup_path, 'a') as zf:
                zf.writestr('backup_manifest.json', json.dumps(manifest, indent=2))

            # Get updated info
            info = manager.get_backup_info(str(backup_path))
        except Exception as e:
            # Invalid backup, delete it
            backup_path.unlink()
            raise HTTPException(status_code=400, detail=f"无效的备份文件: {str(e)}")

        return {
            "success": True,
            "message": "备份导入成功",
            "backup_name": backup_path.name,
            "node_count": info.get("node_count", 0),
            "size_mb": info.get("size_mb", 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to upload backup")
        raise HTTPException(status_code=500, detail=f"上传备份失败: {str(e)}")
