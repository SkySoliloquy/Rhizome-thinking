"""Theme storage management for Rhizome Thinking."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rhizome.config import settings
from rhizome.core.theme_models import Theme, NodeTheme


class ThemeStore:
    """Manages storage and retrieval of themes."""
    
    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """Initialize the theme store.
        
        Args:
            storage_dir: Override the default storage directory
        """
        self.storage_dir = storage_dir or settings.storage_dir
        self.themes_dir = self.storage_dir / "themes"
        self.node_themes_dir = self.storage_dir / "metadata" / "node_themes"
        self.index_path = self.storage_dir / "metadata" / "themes_index.json"
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Load or create index
        self._index = self._load_index()
    
    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        self.node_themes_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_index(self) -> dict:
        """Load the themes index from disk."""
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "themes": {},
            "node_themes": {},
            "last_updated": datetime.now().isoformat()
        }
    
    def _save_index(self) -> None:
        """Save the themes index to disk."""
        self._index["last_updated"] = datetime.now().isoformat()
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)
    
    def _get_theme_path(self, theme_id: str) -> Path:
        """Get the file path for a theme."""
        return self.themes_dir / f"{theme_id}.json"
    
    def _get_node_themes_path(self, node_id: str) -> Path:
        """Get the file path for node themes association."""
        return self.node_themes_dir / f"{node_id}.json"
    
    def save_theme(self, theme: Theme) -> None:
        """Save a theme to storage.

        Args:
            theme: The theme to save
        """
        theme_path = self._get_theme_path(theme.id)
        with open(theme_path, "w", encoding="utf-8") as f:
            json.dump(theme.model_dump(), f, indent=2, ensure_ascii=False)

        # Update index
        self._index["themes"][theme.id] = {
            "id": theme.id,
            "summary": theme.summary[:500],
            "tag": theme.tag,
            "node_count": len(theme.node_ids),
            "updated_at": theme.updated_at.isoformat(),
            "version": getattr(theme, "version", 1),
            "evolution_status": getattr(theme, "evolution_status", "stable")
        }
        self._save_index()
    
    def get_theme(self, theme_id: str) -> Optional[Theme]:
        """Retrieve a theme by ID.

        Args:
            theme_id: The theme ID

        Returns:
            The theme if found, None otherwise
        """
        theme_path = self._get_theme_path(theme_id)

        if not theme_path.exists():
            return None

        with open(theme_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Theme(**data)

    def get_theme_history(self, theme_id: str) -> Optional[list[dict]]:
        """Get evolution history of a theme.

        Args:
            theme_id: The theme ID

        Returns:
            List of version history entries if theme found, None otherwise
        """
        theme = self.get_theme(theme_id)
        if not theme:
            return None

        # Convert ThemeVersion objects to dicts
        history = [
            {
                "version": v.version,
                "summary": v.summary,
                "tag": v.tag,
                "updated_at": v.updated_at.isoformat(),
                "reason": v.reason
            }
            for v in theme.evolution_history
        ]

        return history

    def delete_theme(self, theme_id: str) -> bool:
        """Delete a theme.
        
        Args:
            theme_id: The theme ID
            
        Returns:
            True if the theme was deleted
        """
        theme_path = self._get_theme_path(theme_id)
        
        if not theme_path.exists():
            return False
        
        # Delete file
        theme_path.unlink()
        
        # Update index
        if theme_id in self._index["themes"]:
            del self._index["themes"][theme_id]
            self._save_index()
        
        return True
    
    def list_themes_by_tag(self, tag: str) -> list[Theme]:
        """List all themes for a specific tag.
        
        Args:
            tag: The tag to filter by
            
        Returns:
            List of themes with the specified tag
        """
        themes = []
        for theme_info in self._index["themes"].values():
            if theme_info.get("tag") == tag:
                theme = self.get_theme(theme_info["id"])
                if theme:
                    themes.append(theme)
        
        # Sort by node count (descending) then by update time
        themes.sort(key=lambda t: (-t.node_count, t.updated_at), reverse=False)
        return themes
    
    def get_all_themes(self) -> list[Theme]:
        """Get all themes.
        
        Returns:
            List of all themes
        """
        themes = []
        for theme_id in self._index["themes"].keys():
            theme = self.get_theme(theme_id)
            if theme:
                themes.append(theme)
        return themes
    
    def save_node_themes(self, node_themes: NodeTheme) -> None:
        """Save node themes association.
        
        Args:
            node_themes: The node themes association to save
        """
        node_themes_path = self._get_node_themes_path(node_themes.node_id)
        with open(node_themes_path, "w", encoding="utf-8") as f:
            json.dump(node_themes.model_dump(), f, indent=2, ensure_ascii=False)
        
        # Update index
        self._index["node_themes"][node_themes.node_id] = {
            "node_id": node_themes.node_id,
            "theme_count": len(node_themes.theme_ids),
            "updated_at": node_themes.updated_at.isoformat()
        }
        self._save_index()
    
    def get_node_themes(self, node_id: str) -> Optional[NodeTheme]:
        """Get themes association for a node.
        
        Args:
            node_id: The node ID
            
        Returns:
            Node themes association if found, None otherwise
        """
        node_themes_path = self._get_node_themes_path(node_id)
        
        if not node_themes_path.exists():
            return None
        
        with open(node_themes_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return NodeTheme(**data)
    
    def get_themes_for_node(self, node_id: str) -> list[Theme]:
        """Get all themes that a node belongs to.
        
        Args:
            node_id: The node ID
            
        Returns:
            List of themes
        """
        node_themes = self.get_node_themes(node_id)
        if not node_themes:
            return []
        
        themes = []
        for theme_id in node_themes.theme_ids:
            theme = self.get_theme(theme_id)
            if theme:
                themes.append(theme)
        
        return themes
    
    def add_node_to_theme(self, node_id: str, theme_id: str) -> bool:
        """Add a node to a theme.
        
        Args:
            node_id: The node ID
            theme_id: The theme ID
            
        Returns:
            True if successful
        """
        # Get theme
        theme = self.get_theme(theme_id)
        if not theme:
            return False
        
        # Add node to theme
        theme.add_node(node_id)
        self.save_theme(theme)
        
        # Update node themes
        node_themes = self.get_node_themes(node_id)
        if not node_themes:
            node_themes = NodeTheme(node_id=node_id)
        
        if theme_id not in node_themes.theme_ids:
            node_themes.theme_ids.append(theme_id)
            node_themes.updated_at = datetime.now()
            self.save_node_themes(node_themes)
        
        return True
    
    def remove_node_from_theme(self, node_id: str, theme_id: str) -> bool:
        """Remove a node from a theme.
        
        Args:
            node_id: The node ID
            theme_id: The theme ID
            
        Returns:
            True if successful
        """
        # Get theme
        theme = self.get_theme(theme_id)
        if not theme:
            return False
        
        # Remove node from theme
        theme.remove_node(node_id)
        
        # Delete theme if no nodes left
        if theme.node_count == 0:
            self.delete_theme(theme_id)
        else:
            self.save_theme(theme)
        
        # Update node themes
        node_themes = self.get_node_themes(node_id)
        if node_themes and theme_id in node_themes.theme_ids:
            node_themes.theme_ids.remove(theme_id)
            node_themes.updated_at = datetime.now()
            self.save_node_themes(node_themes)
        
        return True
    
    def get_stats(self) -> dict:
        """Get statistics about stored themes.
        
        Returns:
            Dictionary with statistics
        """
        total_themes = len(self._index["themes"])
        total_node_associations = len(self._index["node_themes"])
        
        # Count themes by tag
        tag_counts = {}
        for theme_info in self._index["themes"].values():
            tag = theme_info.get("tag", "unknown")
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        return {
            "total_themes": total_themes,
            "total_node_associations": total_node_associations,
            "tag_distribution": tag_counts,
            "last_updated": self._index.get("last_updated")
        }
