"""Update management API routes."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from rhizome.core.update_manager import UpdateManager

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateCheckResponse(BaseModel):
    """Response for update check."""
    current_version: str
    current_version_short: str
    update_available: bool = False
    available_count: int = 0
    available_versions: list[dict] = []
    message: str = ""


class UpdatePerformRequest(BaseModel):
    """Request to perform an update."""
    target_version: str = Field(..., description="目标版本commit hash")


class UpdatePerformResponse(BaseModel):
    """Response after triggering an update."""
    success: bool
    message: str
    status: str
    target_version: str
    backup_path: Optional[str] = None
    rolled_back: bool = False


class UpdateStatusResponse(BaseModel):
    """Response for update status."""
    status: str = Field(description="idle/checking/backing_up/updating/restarting/completed/failed/rolled_back")
    progress: int = Field(ge=0, le=100)
    message: str
    current_version: str
    target_version: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class CurrentVersionResponse(BaseModel):
    """Response for current version info."""
    current_version: str
    current_version_short: str
    update_available: bool = False
    available_count: int = 0
    enabled: bool = True
    repo: str = ""
    branch: str = ""


def get_update_manager() -> UpdateManager:
    """Get update manager instance."""
    return UpdateManager()


@router.get("/update/check", response_model=UpdateCheckResponse)
async def check_for_updates():
    """Check for available updates from GitHub stable branch."""
    try:
        manager = get_update_manager()
        versions = manager.check_for_updates()
        info = manager.get_update_info()

        return UpdateCheckResponse(
            current_version=info["current_version"],
            current_version_short=info["current_version_short"],
            update_available=info["update_available"],
            available_count=info["available_count"],
            available_versions=info["available_versions"],
            message=manager.state.get("message", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to check for updates")
        raise HTTPException(status_code=500, detail=f"检查更新失败: {str(e)}")


@router.post("/update/perform", response_model=UpdatePerformResponse)
async def perform_update(request: UpdatePerformRequest):
    """Trigger update to selected version."""
    try:
        manager = get_update_manager()
        result = manager.perform_update(request.target_version)

        return UpdatePerformResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            status=manager.state.get("status", "unknown"),
            target_version=request.target_version,
            backup_path=result.get("backup_path"),
            rolled_back=result.get("rolled_back", False),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to perform update")
        raise HTTPException(status_code=500, detail=f"执行更新失败: {str(e)}")


@router.get("/update/status", response_model=UpdateStatusResponse)
async def get_update_status():
    """Get current update status/progress."""
    try:
        manager = get_update_manager()
        state = manager.state

        return UpdateStatusResponse(
            status=state.get("status", "idle"),
            progress=state.get("progress", 0),
            message=state.get("message", ""),
            current_version=state.get("current_version", ""),
            target_version=state.get("target_version"),
            error=state.get("error"),
            started_at=state.get("started_at"),
            completed_at=state.get("completed_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get update status")
        raise HTTPException(status_code=500, detail=f"获取更新状态失败: {str(e)}")


@router.get("/update/current-version", response_model=CurrentVersionResponse)
async def get_current_version():
    """Get current installed version info."""
    try:
        manager = get_update_manager()
        info = manager.get_update_info()

        return CurrentVersionResponse(
            current_version=info["current_version"],
            current_version_short=info["current_version_short"],
            update_available=info["update_available"],
            available_count=info["available_count"],
            enabled=info["enabled"],
            repo=info["repo"],
            branch=info["branch"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get current version")
        raise HTTPException(status_code=500, detail=f"获取当前版本失败: {str(e)}")
