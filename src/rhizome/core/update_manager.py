"""Update management for Rhizome Thinking.

Handles checking for updates from GitHub, creating pre-update backups,
performing safe git-based updates, and automatic rollback on failure.
"""

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

from rhizome.config import settings
from rhizome.core.backup_manager import BackupManager

logger = logging.getLogger(__name__)


@dataclass
class UpdateVersion:
    """Represents an available update version from GitHub."""

    commit_hash: str
    message: str
    author: str
    date: str
    url: str


@dataclass
class UpdateState:
    """Tracks the current update operation state for polling."""

    status: str = "idle"  # idle, checking, backing_up, updating, restarting, completed, failed, rolled_back
    message: str = ""
    progress: int = 0  # 0-100
    target_version: Optional[str] = None
    backup_path: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_version: str = ""
    available_versions: list[dict] = field(default_factory=list)


class UpdateManager:
    """Manages application updates from a GitHub repository.

    Features:
    - Query GitHub API for commits on the configured branch
    - Get current installed version via git rev-parse HEAD
    - Perform safe update with backup → git fetch/checkout → restart
    - Cache GitHub API responses (5-minute TTL)
    - Graceful error handling with automatic rollback
    - Track update state for progress polling
    """

    def __init__(
        self,
        backup_manager: Optional[BackupManager] = None,
        repo: Optional[str] = None,
        branch: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        """Initialize the update manager.

        Args:
            backup_manager: BackupManager instance for pre-update backups
            repo: GitHub repository in "owner/repo" format (defaults to settings.github_repo)
            branch: Git branch to track (defaults to settings.github_branch)
            token: GitHub Personal Access Token for private repos (defaults to settings.github_token)
        """
        self.backup_manager = backup_manager or BackupManager()
        self.repo = repo or settings.github_repo
        self.branch = branch or settings.github_branch
        self.token = token or settings.github_token
        self.enabled = settings.update_enabled

        # GitHub API cache
        self._cache: dict[str, Any] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
        self._cache_timestamp: Optional[float] = None

        # Update state for polling
        self._state = UpdateState()

        # Project root directory (where .git should be)
        self._project_root = Path(__file__).resolve().parents[3]

    @property
    def state(self) -> dict[str, Any]:
        """Get current update state as a dictionary."""
        return {
            "status": self._state.status,
            "message": self._state.message,
            "progress": self._state.progress,
            "target_version": self._state.target_version,
            "backup_path": self._state.backup_path,
            "error": self._state.error,
            "started_at": self._state.started_at,
            "completed_at": self._state.completed_at,
            "current_version": self._state.current_version or self.get_current_version(),
            "available_versions": self._state.available_versions,
        }

    def _is_cache_valid(self) -> bool:
        """Check if the GitHub API cache is still valid."""
        if self._cache_timestamp is None:
            return False
        elapsed = time.time() - self._cache_timestamp
        return elapsed < self._cache_ttl_seconds

    def _run_git_command(
        self,
        args: list[str],
        cwd: Optional[Path] = None,
        check: bool = True,
        timeout: int = 60,
    ) -> subprocess.CompletedProcess:
        """Run a git command via subprocess.

        Args:
            args: Git command arguments (without "git")
            cwd: Working directory (defaults to project root)
            check: Whether to raise on non-zero exit
            timeout: Command timeout in seconds

        Returns:
            CompletedProcess instance
        """
        cmd = ["git"] + args
        working_dir = cwd or self._project_root

        logger.debug("Running git command: %s in %s", " ".join(cmd), working_dir)

        try:
            result = subprocess.run(
                cmd,
                cwd=str(working_dir),
                capture_output=True,
                text=True,
                check=check,
                timeout=timeout,
                encoding="utf-8",
            )
            return result
        except subprocess.TimeoutExpired as e:
            logger.error("Git command timed out after %ds: %s", timeout, " ".join(cmd))
            raise RuntimeError(f"Git命令超时: {' '.join(cmd)}") from e
        except subprocess.CalledProcessError as e:
            logger.error(
                "Git command failed: %s\nstdout: %s\nstderr: %s",
                " ".join(cmd),
                e.stdout,
                e.stderr,
            )
            raise RuntimeError(
                f"Git命令失败: {e.stderr or e.stdout or 'Unknown error'}"
            ) from e

    def get_current_version(self) -> str:
        """Get the current installed version (git commit hash).

        Returns:
            Current commit hash, or empty string if not a git repo
        """
        try:
            result = self._run_git_command(["rev-parse", "HEAD"], check=False)
            if result.returncode == 0:
                return result.stdout.strip()
            logger.warning("Not a git repository or no commits found")
            return ""
        except Exception as e:
            logger.error("Failed to get current version: %s", e)
            return ""

    def check_for_updates(self, force_refresh: bool = False) -> list[UpdateVersion]:
        """Check for available updates from GitHub.

        Queries the GitHub API for commits on the configured branch that are
        newer than the current installed version.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of available UpdateVersion objects (newer commits)
        """
        if not self.enabled:
            logger.info("Update checking is disabled")
            return []

        if not self.repo or self.repo == "your-username/rhizome-thinking":
            logger.warning("GitHub repository not configured")
            self._state.status = "idle"
            self._state.message = "GitHub仓库未配置，请在.env中设置GITHUB_REPO"
            return []

        self._state.status = "checking"
        self._state.message = "正在检查更新..."
        self._state.progress = 10

        # Use cache if available and valid
        if not force_refresh and self._is_cache_valid() and "commits" in self._cache:
            logger.debug("Using cached GitHub API response")
            commits = self._cache["commits"]
        else:
            # Fetch from GitHub API
            url = f"https://api.github.com/repos/{self.repo}/commits"
            params = {"sha": self.branch, "per_page": 20}

            try:
                logger.info("Fetching commits from GitHub: %s (branch: %s)", self.repo, self.branch)

                # Prepare headers with token for private repos
                headers = {}
                if self.token:
                    headers["Authorization"] = f"token {self.token}"

                response = requests.get(url, params=params, headers=headers, timeout=30)

                # Handle 404 before raise_for_status to provide a clear message
                if response.status_code == 404:
                    logger.warning("GitHub repository not found: %s", self.repo)
                    self._state.status = "idle"
                    self._state.message = "GitHub仓库未找到，请检查配置"
                    self._state.progress = 0
                    return []

                # Handle other HTTP errors
                if not response.ok:
                    status_code = response.status_code
                    logger.error("GitHub API returned HTTP %s for %s", status_code, url)
                    self._state.status = "idle"
                    self._state.message = f"GitHub API错误 ({status_code}): 请检查仓库配置或网络连接"
                    self._state.progress = 0
                    return []

                commits = response.json()

                # Update cache
                self._cache["commits"] = commits
                self._cache_timestamp = time.time()
            except requests.RequestException as e:
                logger.error("Failed to fetch updates from GitHub: %s", e)
                self._state.status = "idle"
                self._state.message = f"GitHub API请求失败: {e}"
                self._state.progress = 0
                return []

        current = self.get_current_version()
        self._state.current_version = current

        available: list[UpdateVersion] = []
        found_current = False

        for commit_data in commits:
            commit_hash = commit_data.get("sha", "")
            commit_info = commit_data.get("commit", {})

            # Stop when we reach the current version
            if current and (commit_hash == current or commit_hash.startswith(current)):
                found_current = True
                break

            # Skip merge commits without meaningful message
            message = commit_info.get("message", "").split("\n")[0].strip()
            if not message:
                continue

            version = UpdateVersion(
                commit_hash=commit_hash,
                message=message,
                author=commit_info.get("author", {}).get("name", "Unknown"),
                date=commit_info.get("author", {}).get("date", ""),
                url=commit_data.get("html_url", ""),
            )
            available.append(version)

        if found_current or not current:
            logger.info("Found %d available update(s)", len(available))
        else:
            logger.warning(
                "Current commit %s not found in recent history; %d commits may be updates",
                current,
                len(available),
            )

        # Update state
        self._state.available_versions = [
            {
                "commit_hash": v.commit_hash,
                "message": v.message,
                "author": v.author,
                "date": v.date,
                "url": v.url,
            }
            for v in available
        ]
        self._state.status = "idle"
        self._state.message = f"发现 {len(available)} 个可用更新" if available else "已是最新版本"
        self._state.progress = 0

        return available

    def _create_pre_update_backup(self) -> Path:
        """Create a backup before performing an update.

        Returns:
            Path to the created backup file

        Raises:
            RuntimeError: If backup creation fails
        """
        self._state.status = "backing_up"
        self._state.message = "正在创建更新前备份..."
        self._state.progress = 20

        try:
            backup_path = self.backup_manager.backup()
            logger.info("Pre-update backup created: %s", backup_path)
            self._state.backup_path = str(backup_path)
            self._state.progress = 35
            return backup_path
        except Exception as e:
            logger.error("Failed to create pre-update backup: %s", e)
            raise RuntimeError(f"更新前备份失败: {e}") from e

    def _restore_backup(self, backup_path: str) -> bool:
        """Restore from a backup file on update failure.

        Args:
            backup_path: Path to the backup file to restore

        Returns:
            True if restore succeeded, False otherwise
        """
        self._state.status = "rolled_back"
        self._state.message = "正在回滚到更新前状态..."
        self._state.progress = 90

        try:
            result = self.backup_manager.restore(backup_path, confirm=True)
            logger.info("Rollback completed: %s", result)
            self._state.message = "回滚完成"
            self._state.progress = 100
            self._state.completed_at = datetime.now().isoformat()
            return True
        except Exception as e:
            logger.error("Rollback failed: %s", e)
            self._state.error = f"回滚失败: {e}"
            self._state.progress = 100
            self._state.completed_at = datetime.now().isoformat()
            return False

    def _restart_service(self) -> None:
        """Restart the application service.

        Detects Docker environment vs direct execution and restarts accordingly.
        """
        self._state.status = "restarting"
        self._state.message = "正在重启服务..."
        self._state.progress = 85

        in_docker = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER", "") == "true"

        if in_docker:
            logger.info("Docker environment detected, attempting docker compose restart")
            try:
                # Try docker compose restart
                subprocess.run(
                    ["docker", "compose", "restart"],
                    cwd=str(self._project_root),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            except Exception as e:
                logger.warning("Docker restart attempt failed: %s", e)
                # Fallback: exit and let Docker restart policy handle it
                logger.info("Exiting process to trigger Docker restart policy")
                os._exit(0)
        else:
            logger.info("Direct execution detected, restarting via uvicorn/process replacement")
            try:
                # Try to find and restart the uvicorn process
                # First, check if there's a pid file or known process
                pid_file = self._project_root / ".rhizome.pid"
                if pid_file.exists():
                    pid = int(pid_file.read_text().strip())
                    logger.info("Sending SIGHUP to process %d", pid)
                    os.kill(pid, 1)  # SIGHUP
                else:
                    # No PID file, we can't gracefully restart
                    logger.warning("No PID file found; cannot auto-restart outside Docker")
                    self._state.message = "更新完成，请手动重启服务"
            except Exception as e:
                logger.error("Restart failed: %s", e)
                self._state.message = "更新完成，请手动重启服务"

    def perform_update(self, target_version: str) -> dict[str, Any]:
        """Perform a safe update to the target version.

        Steps:
        1. Validate target version
        2. Create pre-update backup
        3. Git fetch
        4. Git checkout target commit
        5. Restart service
        6. On failure, rollback backup

        Args:
            target_version: Target commit hash to update to

        Returns:
            Update result dictionary with status and details
        """
        if not self.enabled:
            return {"success": False, "error": "更新功能已禁用"}

        if not self.repo:
            return {"success": False, "error": "GitHub仓库未配置"}

        # Validate target version format (should be a hex string)
        if not target_version or len(target_version) < 7:
            return {"success": False, "error": "无效的目标版本"}

        # Reset state
        self._state = UpdateState()
        self._state.status = "updating"
        self._state.message = "开始更新..."
        self._state.target_version = target_version
        self._state.started_at = datetime.now().isoformat()
        self._state.current_version = self.get_current_version()
        self._state.progress = 5

        backup_path: Optional[Path] = None

        try:
            # Step 1: Create backup
            backup_path = self._create_pre_update_backup()
            self._state.progress = 40

            # Step 2: Git fetch
            self._state.message = "正在获取远程更新..."
            self._state.progress = 50
            self._run_git_command(["fetch", "origin", self.branch])
            logger.info("Git fetch completed for branch %s", self.branch)

            # Step 3: Git checkout target
            self._state.message = f"正在切换到版本 {target_version[:8]}..."
            self._state.progress = 65
            self._run_git_command(["checkout", target_version])
            logger.info("Git checkout completed: %s", target_version)

            # Step 4: Verify checkout succeeded
            current = self.get_current_version()
            if not current.startswith(target_version) and not target_version.startswith(current):
                raise RuntimeError(f"版本切换验证失败: 当前 {current}, 目标 {target_version}")

            self._state.progress = 80
            self._state.message = "代码更新成功，正在重启服务..."

            # Step 5: Restart
            self._restart_service()

            self._state.status = "completed"
            self._state.progress = 100
            self._state.completed_at = datetime.now().isoformat()

            return {
                "success": True,
                "message": "更新成功",
                "previous_version": self._state.current_version,
                "new_version": target_version,
                "backup_path": str(backup_path) if backup_path else None,
            }

        except Exception as e:
            logger.error("Update failed: %s", e)
            self._state.status = "failed"
            self._state.error = str(e)
            self._state.message = f"更新失败: {e}"
            self._state.progress = 100
            self._state.completed_at = datetime.now().isoformat()

            # Attempt rollback
            if backup_path and backup_path.exists():
                logger.info("Attempting rollback from %s", backup_path)
                rollback_success = self._restore_backup(str(backup_path))
                if rollback_success:
                    self._state.message += "（已自动回滚）"
                else:
                    self._state.message += "（回滚失败，请手动恢复）"

            return {
                "success": False,
                "error": str(e),
                "backup_path": str(backup_path) if backup_path else None,
                "rolled_back": self._state.status == "rolled_back",
            }

    def get_update_info(self) -> dict[str, Any]:
        """Get comprehensive update information.

        Returns:
            Dictionary with current version, available updates, and state
        """
        current = self.get_current_version()
        self._state.current_version = current

        # Check if we have cached available versions
        if self._state.available_versions:
            available = self._state.available_versions
        else:
            # Try to get from cache without API call
            if self._is_cache_valid() and "commits" in self._cache:
                available = []
                for commit_data in self._cache["commits"]:
                    commit_hash = commit_data.get("sha", "")
                    if current and (commit_hash == current or commit_hash.startswith(current)):
                        break
                    commit_info = commit_data.get("commit", {})
                    message = commit_info.get("message", "").split("\n")[0].strip()
                    if message:
                        available.append(
                            {
                                "commit_hash": commit_hash,
                                "message": message,
                                "author": commit_info.get("author", {}).get("name", "Unknown"),
                                "date": commit_info.get("author", {}).get("date", ""),
                                "url": commit_data.get("html_url", ""),
                            }
                        )
            else:
                available = []

        return {
            "enabled": self.enabled,
            "repo": self.repo,
            "branch": self.branch,
            "current_version": current,
            "current_version_short": current[:8] if current else "",
            "update_available": len(available) > 0,
            "available_count": len(available),
            "available_versions": available,
            "state": self.state,
            "last_check": (
                datetime.fromtimestamp(self._cache_timestamp).isoformat()
                if self._cache_timestamp
                else None
            ),
        }

    def clear_cache(self) -> None:
        """Clear the GitHub API cache."""
        self._cache.clear()
        self._cache_timestamp = None
        logger.info("Update cache cleared")
