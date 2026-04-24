"""Query engine for semantic search with modifiers."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field

from rhizome.core.models import Node, TagType
from rhizome.core.node_store import NodeStore
from rhizome.retrieval.vector_store import VectorStore


class QueryModifiers(BaseModel):
    """Query modifiers for filtering search results."""
    
    time_range: Optional[Literal["last_week", "last_month", "last_3_months", "all"]] = Field(
        default="all",
        description="Time range filter"
    )
    tags: list[TagType] = Field(
        default_factory=list,
        description="Filter by content tags"
    )
    relation_type: Optional[str] = Field(
        default=None,
        description="Filter by relation type"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results"
    )
    min_similarity: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for results (0.0 - 1.0). Higher values return more relevant results."
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "time_range": "last_month",
                "tags": ["definitive", "needs_thinking"],
                "limit": 20,
                "min_similarity": 0.3
            }
        }


@dataclass
class QueryResult:
    """Single query result."""
    node: Node
    similarity: float
    highlight: Optional[str] = None


class QueryEngine:
    """Two-stage query engine for semantic search."""
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        node_store: Optional[NodeStore] = None
    ) -> None:
        """Initialize the query engine.
        
        Args:
            vector_store: Vector store instance
            node_store: Node store instance
        """
        from rhizome.retrieval.vector_store import get_vector_store
        
        self.vector_store = vector_store or get_vector_store()
        self.node_store = node_store or NodeStore()
    
    async def search(
        self,
        anchor: str,
        modifiers: Optional[QueryModifiers] = None
    ) -> list[QueryResult]:
        """Execute semantic search with modifiers.
        
        Args:
            anchor: Semantic anchor text
            modifiers: Query modifiers for filtering
            
        Returns:
            List of query results
        """
        modifiers = modifiers or QueryModifiers()
        
        # Stage 1: Semantic search
        vector_results = await self.vector_store.search(
            query=anchor,
            limit=modifiers.limit * 2,  # Get more for post-filtering
            tags=modifiers.tags if modifiers.tags else None,
            time_range=modifiers.time_range if modifiers.time_range != "all" else None
        )
        
        # Stage 2: Post-filtering and loading nodes
        results = []
        for node_id, similarity, metadata in vector_results:
            # Filter by minimum similarity threshold first (for performance)
            if similarity < modifiers.min_similarity:
                continue
            
            # Load full node
            node = self.node_store.get(node_id)
            if not node:
                continue
            
            # Filter by tags (post-processing since ChromaDB has limited array support)
            if modifiers.tags:
                if not any(tag in node.tags for tag in modifiers.tags):
                    continue
            
            # Filter by relation type (if specified)
            if modifiers.relation_type:
                has_relation = any(
                    link.relation_type == modifiers.relation_type
                    for link in node.links
                )
                if not has_relation:
                    continue
            
            # Generate highlight
            highlight = self._generate_highlight(node, anchor)
            
            results.append(QueryResult(
                node=node,
                similarity=similarity,
                highlight=highlight
            ))
            
            if len(results) >= modifiers.limit:
                break
        
        return results
    
    def _generate_highlight(self, node: Node, query: str) -> Optional[str]:
        """Generate a highlight snippet for the result.
        
        Args:
            node: The node
            query: Original query
            
        Returns:
            Highlight text or None
        """
        # Use the proposition as highlight
        proposition = node.processed.proposition
        
        # Truncate if too long
        max_length = 150
        if len(proposition) > max_length:
            proposition = proposition[:max_length] + "..."
        
        return proposition
    
    def group_by_tags(self, results: list[QueryResult]) -> dict[str, list[QueryResult]]:
        """Group results by their tags.
        
        Args:
            results: Query results
            
        Returns:
            Dictionary mapping tag to results
        """
        grouped: dict[str, list[QueryResult]] = {}
        
        # Define tag order and display names
        tag_order = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]
        tag_display_names = {
            "definitive": "明确结论",
            "inferred": "推断结论",
            "vague": "模糊感知",
            "needs_thinking": "待思考问题",
            "cross-domain": "跨域连接"
        }
        
        # Initialize groups
        for tag in tag_order:
            grouped[tag_display_names[tag]] = []
        
        # Group results
        for result in results:
            for tag in result.node.tags:
                if tag in tag_display_names:
                    display_name = tag_display_names[tag]
                    if result not in grouped[display_name]:
                        grouped[display_name].append(result)
        
        # Remove empty groups and maintain order
        ordered_grouped = {}
        for tag in tag_order:
            display_name = tag_display_names[tag]
            if grouped[display_name]:
                ordered_grouped[display_name] = grouped[display_name]
        
        return ordered_grouped
    
    def group_by_time(self, results: list[QueryResult]) -> dict[str, list[QueryResult]]:
        """Group results by time periods.
        
        Args:
            results: Query results
            
        Returns:
            Dictionary mapping time period to results
        """
        now = datetime.now()
        grouped: dict[str, list[QueryResult]] = {
            "本周": [],
            "本月": [],
            "近3个月": [],
            "更早": []
        }
        
        for result in results:
            age = now - result.node.timestamp
            
            if age.days < 7:
                grouped["本周"].append(result)
            elif age.days < 30:
                grouped["本月"].append(result)
            elif age.days < 90:
                grouped["近3个月"].append(result)
            else:
                grouped["更早"].append(result)
        
        # Remove empty groups
        return {k: v for k, v in grouped.items() if v}
    
    async def get_related_nodes(
        self,
        node_id: str,
        limit: int = 10
    ) -> list[QueryResult]:
        """Find nodes related to a given node.
        
        Args:
            node_id: The node ID
            limit: Maximum number of results
            
        Returns:
            List of related nodes
        """
        # Get the node
        node = self.node_store.get(node_id)
        if not node:
            return []
        
        # Use the node's proposition as anchor
        anchor = node.processed.proposition
        
        # Search for similar nodes
        results = await self.search(
            anchor=anchor,
            modifiers=QueryModifiers(limit=limit + 1)  # +1 to account for the node itself
        )
        
        # Exclude the node itself
        results = [r for r in results if r.node.id != node_id]
        
        return results[:limit]
    
    def get_stats(self) -> dict:
        """Get query engine statistics.
        
        Returns:
            Dictionary with statistics
        """
        vector_stats = self.vector_store.get_stats()
        node_stats = self.node_store.get_stats()
        
        return {
            "vector_store": vector_stats,
            "node_store": node_stats
        }
