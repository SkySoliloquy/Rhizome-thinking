"""Theme aggregation models for Rhizome Thinking."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer


class Theme(BaseModel):
    """Aggregated theme from multiple nodes."""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Theme unique identifier"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this theme was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When this theme was last updated"
    )
    summary: str = Field(
        ...,
        description="Human-readable summary of the theme",
        min_length=1
    )
    tag: str = Field(
        ...,
        description="Primary tag this theme belongs to"
    )
    node_ids: list[str] = Field(
        default_factory=list,
        description="IDs of nodes that belong to this theme"
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords extracted from related nodes"
    )
    
    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
    
    def add_node(self, node_id: str) -> None:
        """Add a node to this theme if not already present."""
        if node_id not in self.node_ids:
            self.node_ids.append(node_id)
            self.updated_at = datetime.now()
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node from this theme."""
        if node_id in self.node_ids:
            self.node_ids.remove(node_id)
            self.updated_at = datetime.now()
            return True
        return False
    
    @property
    def node_count(self) -> int:
        """Get number of nodes in this theme."""
        return len(self.node_ids)


class NodeTheme(BaseModel):
    """Association between a node and its themes."""
    
    node_id: str = Field(
        ...,
        description="ID of the node"
    )
    theme_ids: list[str] = Field(
        default_factory=list,
        description="IDs of themes this node belongs to"
    )
    extracted_themes: list[str] = Field(
        default_factory=list,
        description="Raw theme strings extracted from the node"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When this association was last updated"
    )
    
    @field_serializer("updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()


class AggregatedSearchResult(BaseModel):
    """Search result aggregated by themes."""
    
    tag: str = Field(
        ...,
        description="Tag/category name"
    )
    tag_display_name: str = Field(
        ...,
        description="Human-readable tag name"
    )
    themes: list[Theme] = Field(
        default_factory=list,
        description="Themes in this category"
    )
    ungrouped_nodes: list[str] = Field(
        default_factory=list,
        description="Node IDs that couldn't be grouped into themes"
    )
