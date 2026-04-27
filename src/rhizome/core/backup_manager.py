"""Backup and restore management for Rhizome Thinking."""

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from rhizome.config import settings


class BackupManager:
    """Manages backup and restore operations."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """Initialize the backup manager.

        Args:
            storage_dir: Override the default storage directory
        """
        self.storage_dir = storage_dir or settings.storage_dir
        self.nodes_dir = self.storage_dir / "nodes"
        self.metadata_dir = self.storage_dir / "metadata"
        self.themes_dir = self.storage_dir / "themes"
        self.node_themes_dir = self.metadata_dir / "node_themes"
        self.backups_dir = self.storage_dir / "backups"

        # Ensure backups directory exists
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def _generate_backup_name(self) -> str:
        """Generate a backup file name based on current timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"backup_{timestamp}.zip"

    def _get_backup_manifest(self, node_count: int) -> dict:
        """Generate backup manifest metadata."""
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "node_count": node_count,
            "backup_type": "full",
            "includes_vectors": False,
            "app_version": "0.2.0"
        }

    def backup(self, output_path: Optional[str] = None) -> Path:
        """Create a backup of all user data.

        Args:
            output_path: Optional custom output path for the backup file

        Returns:
            Path to the created backup file
        """
        # Determine backup file path
        if output_path:
            backup_path = Path(output_path)
        else:
            backup_path = self.backups_dir / self._generate_backup_name()

        # Ensure parent directory exists
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Count nodes for manifest
        node_files = list(self.nodes_dir.glob("*.md")) if self.nodes_dir.exists() else []
        node_count = len(node_files)

        # Create backup manifest
        manifest = self._get_backup_manifest(node_count)

        # Create ZIP archive
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Write manifest
            zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

            # Add node files
            if self.nodes_dir.exists():
                for node_file in node_files:
                    arcname = f"nodes/{node_file.name}"
                    zf.write(node_file, arcname)

            # Add metadata files (root level only)
            if self.metadata_dir.exists():
                for meta_file in self.metadata_dir.glob("*.json"):
                    arcname = f"metadata/{meta_file.name}"
                    zf.write(meta_file, arcname)

            # Add node_themes files
            if self.node_themes_dir.exists():
                for nt_file in self.node_themes_dir.glob("*.json"):
                    arcname = f"metadata/node_themes/{nt_file.name}"
                    zf.write(nt_file, arcname)

            # Add theme files
            if self.themes_dir.exists():
                for theme_file in self.themes_dir.glob("*.json"):
                    arcname = f"themes/{theme_file.name}"
                    zf.write(theme_file, arcname)

        return backup_path

    def restore(self, backup_path: str, confirm: bool = False) -> dict:
        """Restore from a backup file.

        Args:
            backup_path: Path to the backup file
            confirm: If True, clear existing data before restore

        Returns:
            Restoration result information
        """
        backup_file = Path(backup_path)

        if not backup_file.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        # Validate backup
        manifest = self._validate_backup(backup_file)

        # Clear existing data if confirmed
        if confirm:
            self._clear_existing_data()

        # Extract backup
        with zipfile.ZipFile(backup_file, 'r') as zf:
            for item in zf.namelist():
                if item == "backup_manifest.json":
                    continue
                parts = item.split("/")
                if len(parts) >= 2 and parts[-1]:
                    target_path = self.storage_dir / item
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(item) as src, open(target_path, 'wb') as dst:
                        dst.write(src.read())

        return {
            "success": True,
            "restored_nodes": manifest.get("node_count", 0),
            "backup_date": manifest.get("created_at"),
            "message": "备份恢复成功"
        }

    def _validate_backup(self, backup_file: Path) -> dict:
        """Validate backup file integrity.

        Args:
            backup_file: Path to the backup file

        Returns:
            Backup manifest if valid

        Raises:
            ValueError: If backup is invalid
        """
        try:
            with zipfile.ZipFile(backup_file, 'r') as zf:
                # Check for manifest
                if "backup_manifest.json" not in zf.namelist():
                    raise ValueError("备份文件缺少清单文件")

                # Read and validate manifest
                with zf.open("backup_manifest.json") as f:
                    manifest = json.loads(f.read().decode('utf-8'))

                # Validate required fields
                required_fields = ["version", "created_at", "node_count"]
                for field in required_fields:
                    if field not in manifest:
                        raise ValueError(f"备份清单缺少必要字段: {field}")

                # Check for nodes directory in backup
                has_nodes = any(name.startswith("nodes/") for name in zf.namelist())
                if not has_nodes:
                    raise ValueError("备份文件中没有找到节点数据")

                return manifest

        except zipfile.BadZipFile:
            raise ValueError("无效的备份文件格式")

    def _clear_existing_data(self) -> None:
        """Clear all existing node, theme, and metadata files."""
        # Clear nodes
        if self.nodes_dir.exists():
            for f in self.nodes_dir.glob("*.md"):
                f.unlink()

        # Clear metadata (root level JSON files)
        if self.metadata_dir.exists():
            for f in self.metadata_dir.glob("*.json"):
                f.unlink()

        # Clear node_themes
        if self.node_themes_dir.exists():
            for f in self.node_themes_dir.glob("*.json"):
                f.unlink()

        # Clear themes
        if self.themes_dir.exists():
            for f in self.themes_dir.glob("*.json"):
                f.unlink()

    def list_backups(self) -> list[dict]:
        """List all available backups, sorted by creation time (newest first).

        Returns:
            List of backup information dictionaries
        """
        backups = []

        if not self.backups_dir.exists():
            return backups

        for backup_file in self.backups_dir.glob("*.zip"):
            try:
                info = self.get_backup_info(str(backup_file))
                backups.append(info)
            except Exception:
                # Skip invalid backup files
                continue

        # Sort by created_at timestamp, newest first
        backups.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return backups

    def get_backup_info(self, backup_path: str) -> dict:
        """Get detailed information about a backup.

        Args:
            backup_path: Path to the backup file

        Returns:
            Backup information dictionary
        """
        backup_file = Path(backup_path)

        if not backup_file.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        # Get file size
        size_bytes = backup_file.stat().st_size
        size_mb = round(size_bytes / (1024 * 1024), 2)

        # Read manifest
        with zipfile.ZipFile(backup_file, 'r') as zf:
            with zf.open("backup_manifest.json") as f:
                manifest = json.loads(f.read().decode('utf-8'))

        return {
            "name": backup_file.name,
            "path": str(backup_file),
            "created_at": manifest.get("created_at"),
            "node_count": manifest.get("node_count", 0),
            "backup_type": manifest.get("backup_type", "unknown"),
            "version": manifest.get("version", "unknown"),
            "size_mb": size_mb,
            "includes_vectors": manifest.get("includes_vectors", False)
        }

    def delete_backup(self, backup_name: str) -> bool:
        """Delete a backup file.

        Args:
            backup_name: Name of the backup file

        Returns:
            True if deleted successfully
        """
        # Handle both full path and just filename
        if "/" in backup_name or "\\" in backup_name:
            backup_file = Path(backup_name)
        else:
            backup_file = self.backups_dir / backup_name

        if not backup_file.exists():
            return False

        backup_file.unlink()
        return True
