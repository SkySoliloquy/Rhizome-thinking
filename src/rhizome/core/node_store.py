"""Node storage management for Rhizome Thinking."""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Optional

from rhizome.config import settings
from rhizome.core.models import Node


class NodeStore:
    """Manages storage and retrieval of nodes."""
    
    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """Initialize the node store.
        
        Args:
            storage_dir: Override the default storage directory
        """
        self.storage_dir = storage_dir or settings.storage_dir
        self.nodes_dir = self.storage_dir / "nodes"
        self.metadata_dir = self.storage_dir / "metadata"
        self.index_path = self.metadata_dir / "nodes_index.json"
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Load or create index
        self._index = self._load_index()
    
    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_index(self) -> dict:
        """Load the nodes index from disk."""
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"nodes": {}, "last_updated": datetime.now().isoformat()}
    
    def _save_index(self) -> None:
        """Save the nodes index to disk (atomic write)."""
        self._index["last_updated"] = datetime.now().isoformat()
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".json", prefix=".nodes_index.", dir=self.metadata_dir
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self._index, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.index_path)
        except Exception:
            os.unlink(tmp_path)
            raise
    
    def _get_node_path(self, node_id: str) -> Path:
        """Get the file path for a node."""
        return self.nodes_dir / f"{node_id}.md"
    
    def _update_index(self, node: Node) -> None:
        """Update the index with node metadata."""
        self._index["nodes"][node.id] = {
            "id": node.id,
            "timestamp": node.timestamp.isoformat(),
            "proposition": node.processed.proposition,
            "tags": node.tags,
            "link_count": len(node.links),
            "confirmed_link_count": sum(1 for link in node.links if link.confirmed),
            "has_refined_content": node.refined_content is not None,
            "refined_content_version": node.refined_content_version,
        }
        self._save_index()
    
    def save(self, node: Node) -> None:
        """Save a node to storage.

        Uses atomic write (temp file + rename) to prevent corruption from
        concurrent writes or crashes mid-write.

        Args:
            node: The node to save
        """
        # Atomic write: write to temp file then rename
        node_path = self._get_node_path(node.id)
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".md", prefix=f".{node.id}.", dir=self.nodes_dir
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(node.to_markdown())
            os.replace(tmp_path, node_path)  # Atomic on POSIX & Windows
        except Exception:
            os.unlink(tmp_path)
            raise

        # Update index
        self._update_index(node)
    
    def get(self, node_id: str) -> Optional[Node]:
        """Retrieve a node by ID.

        Args:
            node_id: The node ID

        Returns:
            The node if found, None otherwise
        """
        node_path = self._get_node_path(node_id)

        if not node_path.exists():
            return None

        try:
            with open(node_path, "r", encoding="utf-8") as f:
                content = f.read()
            return Node.from_markdown(content)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to parse node {node_id}: {e}")
            return None
    
    def exists(self, node_id: str) -> bool:
        """Check if a node exists.
        
        Args:
            node_id: The node ID
            
        Returns:
            True if the node exists
        """
        return self._get_node_path(node_id).exists()
    
    def delete(self, node_id: str) -> bool:
        """Delete a node.
        
        Args:
            node_id: The node ID
            
        Returns:
            True if the node was deleted
        """
        node_path = self._get_node_path(node_id)
        
        if not node_path.exists():
            return False
        
        # Delete file
        node_path.unlink()
        
        # Update index
        if node_id in self._index["nodes"]:
            del self._index["nodes"][node_id]
            self._save_index()
        
        return True
    
    def list_all(self, limit: Optional[int] = None, offset: int = 0) -> list[Node]:
        """List all nodes.
        
        Args:
            limit: Maximum number of nodes to return
            offset: Number of nodes to skip
            
        Returns:
            List of nodes
        """
        # Get sorted node IDs from index (by timestamp, newest first)
        sorted_entries = sorted(
            self._index["nodes"].values(),
            key=lambda x: x["timestamp"],
            reverse=True
        )
        
        # Apply offset and limit
        if offset:
            sorted_entries = sorted_entries[offset:]
        if limit:
            sorted_entries = sorted_entries[:limit]
        
        # Load nodes
        nodes = []
        for entry in sorted_entries:
            node = self.get(entry["id"])
            if node:
                nodes.append(node)
        
        return nodes
    
    def list_by_tag(self, tag: str, limit: Optional[int] = None) -> list[Node]:
        """List nodes by tag.
        
        Args:
            tag: The tag to filter by
            limit: Maximum number of nodes to return
            
        Returns:
            List of nodes with the specified tag
        """
        matching = []
        for entry in self._index["nodes"].values():
            if tag in entry.get("tags", []):
                node = self.get(entry["id"])
                if node:
                    matching.append(node)
                    if limit and len(matching) >= limit:
                        break
        
        return matching
    
    def search_by_proposition(self, query: str, limit: int = 10) -> list[tuple[Node, float]]:
        """Simple keyword search in propositions.
        
        This is a temporary solution for Stage 1.
        Stage 2 will use semantic search via ChromaDB.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of (node, score) tuples
        """
        query_lower = query.lower()
        results = []
        
        for entry in self._index["nodes"].values():
            proposition = entry.get("proposition", "").lower()
            if query_lower in proposition:
                # Simple scoring: exact match gets higher score
                score = 1.0 if query_lower == proposition else 0.5
                node = self.get(entry["id"])
                if node:
                    results.append((node, score))
        
        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:limit]
    
    def update_link(self, node_id: str, target_id: str, confirmed: bool) -> bool:
        """Update the confirmation status of a link.
        
        Args:
            node_id: Source node ID
            target_id: Target node ID
            confirmed: New confirmation status
            
        Returns:
            True if the link was updated
        """
        node = self.get(node_id)
        if not node:
            return False
        
        for link in node.links:
            if link.target_id == target_id:
                link.confirmed = confirmed
                self.save(node)
                return True
        
        return False
    
    def add_link(
        self,
        node_id: str,
        target_id: str,
        relation_type: str,
        strength: float,
        confirmed: bool = False
    ) -> bool:
        """Add a new link to a node.
        
        Args:
            node_id: Source node ID
            target_id: Target node ID
            relation_type: Type of relationship
            strength: Connection strength (0.0 - 1.0)
            confirmed: Whether the link is confirmed
            
        Returns:
            True if the link was added
        """
        from rhizome.core.models import Link
        
        node = self.get(node_id)
        if not node:
            return False
        
        # Check if link already exists
        for link in node.links:
            if link.target_id == target_id:
                return False
        
        # Add new link
        link = Link(
            target_id=target_id,
            relation_type=relation_type,  # type: ignore
            strength=strength,
            confirmed=confirmed
        )
        node.links.append(link)
        self.save(node)
        
        return True
    
    def reload(self) -> None:
        """Reload the index from disk (hot reload support)."""
        self._index = self._load_index()

    def update_node(
        self,
        node_id: str,
        proposition: Optional[str] = None,
        raw_input: Optional[str] = None,
        tags: Optional[list[str]] = None,
        open_questions: Optional[list[str]] = None,
        source_title: Optional[str] = None,
        source_location: Optional[str] = None,
        auto_save: bool = True
    ) -> Optional[Node]:
        """Update node fields.

        Args:
            node_id: The node ID
            proposition: New proposition text
            raw_input: New raw input text
            tags: New tags list
            open_questions: New open questions list
            source_title: New source title
            source_location: New source location
            auto_save: Whether to save immediately

        Returns:
            Updated node if found, None otherwise
        """
        node = self.get(node_id)
        if not node:
            return None

        # Update fields if provided
        if proposition is not None:
            node.processed.proposition = proposition
        if raw_input is not None:
            node.raw_input = raw_input
        if tags is not None:
            node.tags = tags
        if open_questions is not None:
            node.processed.open_questions = open_questions
        if source_title is not None:
            node.source.title = source_title
        if source_location is not None:
            node.source.location = source_location

        if auto_save:
            self.save(node)

        return node

    def update_refined_content(
        self,
        node_id: str,
        refined_content: str,
        auto_save: bool = True
    ) -> Optional[Node]:
        """Update the refined content of a node.

        Args:
            node_id: The node ID
            refined_content: New refined content
            auto_save: Whether to save immediately

        Returns:
            Updated node if found, None otherwise
        """
        from datetime import datetime

        node = self.get(node_id)
        if not node:
            return None

        node.refined_content = refined_content
        node.refined_content_version += 1
        node.last_refined_at = datetime.now()

        if auto_save:
            self.save(node)

        return node

    def search_by_raw_content(
        self,
        query: str,
        limit: int = 10,
        fuzzy: bool = False
    ) -> list[tuple[Node, float]]:
        """Search nodes by raw content.

        Args:
            query: Search query
            limit: Maximum results
            fuzzy: Enable fuzzy matching

        Returns:
            List of (node, score) tuples
        """
        results = []
        query_lower = query.lower()

        for entry in self._index["nodes"].values():
            node = self.get(entry["id"])
            if not node:
                continue

            raw_lower = node.raw_input.lower()

            if fuzzy:
                if self._fuzzy_match(query_lower, raw_lower):
                    score = 0.6
                    results.append((node, score))
            else:
                if query_lower in raw_lower:
                    score = 0.8
                    results.append((node, score))

            if len(results) >= limit:
                break

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        """Check if pattern matches text fuzzily (characters in order)."""
        pattern_idx = 0
        for char in text:
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                pattern_idx += 1
        return pattern_idx == len(pattern)

    def search_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> list[tuple[Node, float]]:
        """Search nodes by date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            limit: Maximum results

        Returns:
            List of (node, score) tuples (score=1.0 since filtering is by date, not relevance)
        """
        results = []

        for entry in self._index["nodes"].values():
            timestamp = datetime.fromisoformat(entry["timestamp"])

            if start_date and timestamp < start_date:
                continue
            if end_date and timestamp > end_date:
                continue

            node = self.get(entry["id"])
            if node:
                results.append((node, 1.0))

            if len(results) >= limit:
                break

        results.sort(key=lambda x: x[0].timestamp, reverse=True)
        return results

    def precise_search(
        self,
        proposition_query: Optional[str] = None,
        raw_content_query: Optional[str] = None,
        tags: Optional[list[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: Literal["time", "proposition"] = "time",
        limit: int = 100
    ) -> list[Node]:
        """Precise search with combined conditions (AND logic).

        Args:
            proposition_query: Search in proposition
            raw_content_query: Search in raw content
            tags: Filter by tags
            start_date: Start date filter
            end_date: End date filter
            sort_by: Sort field
            limit: Maximum results

        Returns:
            List of matching nodes
        """
        results = []

        for entry in self._index["nodes"].values():
            node = self.get(entry["id"])
            if not node:
                continue

            # Check proposition query
            if proposition_query:
                prop_lower = node.processed.proposition.lower()
                if proposition_query.lower() not in prop_lower:
                    continue

            # Check raw content query
            if raw_content_query:
                raw_lower = node.raw_input.lower()
                if raw_content_query.lower() not in raw_lower:
                    continue

            # Check tags
            if tags:
                if not any(tag in node.tags for tag in tags):
                    continue

            # Check date range
            if start_date or end_date:
                timestamp = datetime.fromisoformat(entry["timestamp"])
                if start_date and timestamp < start_date:
                    continue
                if end_date and timestamp > end_date:
                    continue

            results.append(node)

            if len(results) >= limit:
                break

        # Sort results
        if sort_by == "time":
            results.sort(key=lambda n: n.timestamp, reverse=True)
        elif sort_by == "proposition":
            results.sort(key=lambda n: n.processed.proposition)

        return results

    def get_stats(self) -> dict:
        """Get statistics about the stored nodes.

        Returns:
            Dictionary with statistics
        """
        total_nodes = len(self._index["nodes"])
        total_links = sum(
            entry.get("link_count", 0)
            for entry in self._index["nodes"].values()
        )
        confirmed_links = sum(
            entry.get("confirmed_link_count", 0)
            for entry in self._index["nodes"].values()
        )

        # Count tags
        tag_counts = {}
        for entry in self._index["nodes"].values():
            for tag in entry.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return {
            "total_nodes": total_nodes,
            "total_links": total_links,
            "confirmed_links": confirmed_links,
            "pending_links": total_links - confirmed_links,
            "tag_counts": tag_counts,
            "last_updated": self._index.get("last_updated"),
        }
