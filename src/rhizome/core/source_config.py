"""Source type configuration management."""

import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from rhizome.config import settings


class SourceTypeConfig(BaseModel):
    """Configuration for a custom source type."""
    
    id: str = Field(..., description="Unique identifier for the source type")
    name: str = Field(..., description="Display name for the source type")
    description: Optional[str] = Field(default=None, description="Optional description")
    is_builtin: bool = Field(default=False, description="Whether this is a built-in type")


class SourceConfigManager:
    """Manages custom source type configurations."""
    
    # Built-in source types that cannot be deleted
    BUILTIN_SOURCES = [
        SourceTypeConfig(id="original", name="原创想法", description="个人原创思考", is_builtin=True),
        SourceTypeConfig(id="book", name="书籍", description="书籍阅读笔记", is_builtin=True),
        SourceTypeConfig(id="paper", name="论文", description="学术论文笔记", is_builtin=True),
        SourceTypeConfig(id="article", name="文章", description="网络文章或博客", is_builtin=True),
    ]
    
    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize the source config manager.
        
        Args:
            config_path: Path to the config file, defaults to storage/metadata/source_config.json
        """
        self.config_path = config_path or (settings.metadata_dir / "source_config.json")
        self._custom_sources: list[SourceTypeConfig] = []
        self._load_config()
    
    def _load_config(self) -> None:
        """Load custom source types from config file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._custom_sources = [
                        SourceTypeConfig(**source) for source in data.get("custom_sources", [])
                    ]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading source config: {e}")
                self._custom_sources = []
    
    def _save_config(self) -> None:
        """Save custom source types to config file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "custom_sources": [
                source.model_dump() for source in self._custom_sources
            ]
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_all_sources(self) -> list[SourceTypeConfig]:
        """Get all source types (built-in + custom).
        
        Returns:
            List of all source type configurations
        """
        return self.BUILTIN_SOURCES + self._custom_sources
    
    def get_source(self, source_id: str) -> Optional[SourceTypeConfig]:
        """Get a specific source type by ID.
        
        Args:
            source_id: The source type identifier
            
        Returns:
            SourceTypeConfig if found, None otherwise
        """
        for source in self.get_all_sources():
            if source.id == source_id:
                return source
        return None
    
    def add_custom_source(self, name: str, description: Optional[str] = None) -> SourceTypeConfig:
        """Add a new custom source type.
        
        Args:
            name: Display name for the source type
            description: Optional description
            
        Returns:
            The created SourceTypeConfig
            
        Raises:
            ValueError: If a source with the same ID already exists
        """
        # Generate ID from name (lowercase, alphanumeric only)
        import re
        source_id = re.sub(r'[^\w\s]', '', name).lower().replace(' ', '_')
        
        # Check if ID already exists
        if self.get_source(source_id):
            raise ValueError(f"Source type with ID '{source_id}' already exists")
        
        source = SourceTypeConfig(
            id=source_id,
            name=name,
            description=description,
            is_builtin=False
        )
        
        self._custom_sources.append(source)
        self._save_config()
        return source
    
    def update_custom_source(self, source_id: str, name: Optional[str] = None, 
                           description: Optional[str] = None) -> Optional[SourceTypeConfig]:
        """Update an existing custom source type.
        
        Args:
            source_id: The source type identifier
            name: New display name (optional)
            description: New description (optional)
            
        Returns:
            Updated SourceTypeConfig if found, None otherwise
            
        Raises:
            ValueError: If trying to update a built-in source
        """
        # Check if it's a built-in source
        builtin_ids = [s.id for s in self.BUILTIN_SOURCES]
        if source_id in builtin_ids:
            raise ValueError(f"Cannot modify built-in source type '{source_id}'")
        
        for source in self._custom_sources:
            if source.id == source_id:
                if name:
                    source.name = name
                if description is not None:
                    source.description = description
                self._save_config()
                return source
        
        return None
    
    def delete_custom_source(self, source_id: str) -> bool:
        """Delete a custom source type.
        
        Args:
            source_id: The source type identifier
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            ValueError: If trying to delete a built-in source
        """
        # Check if it's a built-in source
        builtin_ids = [s.id for s in self.BUILTIN_SOURCES]
        if source_id in builtin_ids:
            raise ValueError(f"Cannot delete built-in source type '{source_id}'")
        
        for i, source in enumerate(self._custom_sources):
            if source.id == source_id:
                del self._custom_sources[i]
                self._save_config()
                return True
        
        return False
    
    def is_valid_source_type(self, source_type: str) -> bool:
        """Check if a source type is valid.
        
        Args:
            source_type: The source type identifier to check
            
        Returns:
            True if valid, False otherwise
        """
        return self.get_source(source_type) is not None


# Global instance
_source_config_manager: Optional[SourceConfigManager] = None


def get_source_config_manager() -> SourceConfigManager:
    """Get the global source config manager instance."""
    global _source_config_manager
    if _source_config_manager is None:
        _source_config_manager = SourceConfigManager()
    return _source_config_manager
