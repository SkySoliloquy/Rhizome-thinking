"""Relationship suggestion storage for Rhizome Thinking."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rhizome.config import settings
from rhizome.core.relationship_models import (
    RelationshipBatch,
    RelationshipStats,
    RelationshipSuggestion,
    SuggestionStatus,
)


class RelationshipStore:
    """Manages storage and retrieval of relationship suggestions."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """Initialize the relationship store.

        Args:
            storage_dir: Override the default storage directory
        """
        self.storage_dir = storage_dir or settings.storage_dir
        self.suggestions_dir = self.storage_dir / "metadata" / "relationships"
        self.index_path = self.storage_dir / "metadata" / "relationships_index.json"

        # Ensure directories exist
        self._ensure_directories()

        # Load or create index
        self._index = self._load_index()

    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.suggestions_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict:
        """Load the relationships index from disk."""
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "suggestions": {},
            "batches": {},
            "stats": {
                "total": 0,
                "pending": 0,
                "confirmed": 0,
                "rejected": 0,
            },
            "last_updated": datetime.now().isoformat(),
        }

    def _save_index(self) -> None:
        """Save the relationships index to disk."""
        self._index["last_updated"] = datetime.now().isoformat()
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _get_suggestion_path(self, suggestion_id: str) -> Path:
        """Get the file path for a suggestion."""
        return self.suggestions_dir / f"{suggestion_id}.json"

    def _get_batch_path(self, node_id: str) -> Path:
        """Get the file path for a node's suggestion batch."""
        return self.suggestions_dir / f"batch_{node_id}.json"

    def save_suggestion(self, suggestion: RelationshipSuggestion) -> None:
        """Save a single suggestion to storage.

        Args:
            suggestion: The suggestion to save
        """
        suggestion_path = self._get_suggestion_path(suggestion.id)
        with open(suggestion_path, "w", encoding="utf-8") as f:
            json.dump(suggestion.model_dump(), f, indent=2, ensure_ascii=False)

        # Update index
        self._index["suggestions"][suggestion.id] = {
            "id": suggestion.id,
            "source_id": suggestion.source_id,
            "target_id": suggestion.target_id,
            "target_type": suggestion.target_type,
            "relation_type": suggestion.relation_type,
            "status": suggestion.status.value,
            "confidence": suggestion.confidence,
            "strength": suggestion.strength,
            "created_at": suggestion.created_at.isoformat(),
        }
        self._update_stats()
        self._save_index()

    def save_batch(self, batch: RelationshipBatch) -> None:
        """Save a batch of suggestions for a node.

        Args:
            batch: The batch to save
        """
        batch_path = self._get_batch_path(batch.node_id)
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump(batch.model_dump(), f, indent=2, ensure_ascii=False)

        # Save individual suggestions and update index
        for suggestion in batch.suggestions:
            self.save_suggestion(suggestion)

        # Update batch index
        self._index["batches"][batch.node_id] = {
            "node_id": batch.node_id,
            "suggestion_count": len(batch.suggestions),
            "pending_count": batch.pending_count,
            "confirmed_count": batch.confirmed_count,
            "rejected_count": batch.rejected_count,
            "analyzed_at": batch.analyzed_at.isoformat(),
        }
        self._save_index()

    def get_suggestion(self, suggestion_id: str) -> Optional[RelationshipSuggestion]:
        """Retrieve a suggestion by ID.

        Args:
            suggestion_id: The suggestion ID

        Returns:
            The suggestion if found, None otherwise
        """
        suggestion_path = self._get_suggestion_path(suggestion_id)

        if not suggestion_path.exists():
            return None

        with open(suggestion_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return RelationshipSuggestion(**data)

    def get_batch(self, node_id: str) -> Optional[RelationshipBatch]:
        """Retrieve a suggestion batch for a node.

        Args:
            node_id: The node ID

        Returns:
            The batch if found, None otherwise
        """
        batch_path = self._get_batch_path(node_id)

        if not batch_path.exists():
            return None

        with open(batch_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return RelationshipBatch(**data)

    def get_suggestions_for_node(
        self,
        node_id: str,
        status: Optional[SuggestionStatus] = None,
    ) -> list[RelationshipSuggestion]:
        """Get all suggestions for a specific node.

        Args:
            node_id: The source node ID
            status: Optional filter by status

        Returns:
            List of suggestions
        """
        suggestions = []
        for suggestion_info in self._index["suggestions"].values():
            if suggestion_info["source_id"] == node_id:
                if status is None or suggestion_info["status"] == status.value:
                    suggestion = self.get_suggestion(suggestion_info["id"])
                    if suggestion:
                        suggestions.append(suggestion)

        # Sort by confidence (descending)
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return suggestions

    def get_pending_suggestions(self, limit: int = 100) -> list[RelationshipSuggestion]:
        """Get pending suggestions awaiting review.

        Args:
            limit: Maximum number of suggestions to return

        Returns:
            List of pending suggestions
        """
        suggestions = []
        for suggestion_info in self._index["suggestions"].values():
            if suggestion_info["status"] == SuggestionStatus.PENDING.value:
                suggestion = self.get_suggestion(suggestion_info["id"])
                if suggestion:
                    suggestions.append(suggestion)

        # Sort by confidence (descending) then by creation time
        suggestions.sort(key=lambda s: (-s.confidence, s.created_at))
        return suggestions[:limit]

    def get_suggestions_for_target(
        self,
        target_id: str,
        target_type: Optional[str] = None,
    ) -> list[RelationshipSuggestion]:
        """Get all suggestions targeting a specific node or theme.

        Args:
            target_id: The target ID
            target_type: Optional filter by target type

        Returns:
            List of suggestions
        """
        suggestions = []
        for suggestion_info in self._index["suggestions"].values():
            if suggestion_info["target_id"] == target_id:
                if target_type is None or suggestion_info["target_type"] == target_type:
                    suggestion = self.get_suggestion(suggestion_info["id"])
                    if suggestion:
                        suggestions.append(suggestion)

        return suggestions

    def update_suggestion_status(
        self,
        suggestion_id: str,
        status: SuggestionStatus,
        reviewed_by: str = "user",
    ) -> bool:
        """Update the status of a suggestion.

        Args:
            suggestion_id: The suggestion ID
            status: New status
            reviewed_by: Who reviewed the suggestion

        Returns:
            True if successful
        """
        suggestion = self.get_suggestion(suggestion_id)
        if not suggestion:
            return False

        # Update suggestion
        if status == SuggestionStatus.CONFIRMED:
            suggestion.confirm(reviewed_by)
        elif status == SuggestionStatus.REJECTED:
            suggestion.reject(reviewed_by)
        else:
            suggestion.status = status
            suggestion.reviewed_at = datetime.now()
            suggestion.reviewed_by = reviewed_by

        # Save updated suggestion
        self.save_suggestion(suggestion)

        # Update batch if exists
        batch = self.get_batch(suggestion.source_id)
        if batch:
            for i, s in enumerate(batch.suggestions):
                if s.id == suggestion_id:
                    batch.suggestions[i] = suggestion
                    break
            self.save_batch(batch)

        return True

    def delete_suggestion(self, suggestion_id: str) -> bool:
        """Delete a suggestion.

        Args:
            suggestion_id: The suggestion ID

        Returns:
            True if the suggestion was deleted
        """
        suggestion_path = self._get_suggestion_path(suggestion_id)

        if not suggestion_path.exists():
            return False

        # Delete file
        suggestion_path.unlink()

        # Update index
        if suggestion_id in self._index["suggestions"]:
            del self._index["suggestions"][suggestion_id]
            self._update_stats()
            self._save_index()

        return True

    def _update_stats(self) -> None:
        """Update statistics in the index."""
        total = len(self._index["suggestions"])
        pending = sum(
            1
            for s in self._index["suggestions"].values()
            if s["status"] == SuggestionStatus.PENDING.value
        )
        confirmed = sum(
            1
            for s in self._index["suggestions"].values()
            if s["status"] == SuggestionStatus.CONFIRMED.value
        )
        rejected = sum(
            1
            for s in self._index["suggestions"].values()
            if s["status"] == SuggestionStatus.REJECTED.value
        )

        self._index["stats"] = {
            "total": total,
            "pending": pending,
            "confirmed": confirmed,
            "rejected": rejected,
        }

    def get_stats(self) -> RelationshipStats:
        """Get statistics about stored suggestions.

        Returns:
            Statistics object
        """
        stats = self._index.get("stats", {})
        suggestions = list(self._index["suggestions"].values())

        # Count by relation type
        by_relation_type = {}
        by_target_type = {}
        total_confidence = 0.0
        total_strength = 0.0

        for s in suggestions:
            relation_type = s.get("relation_type", "unknown")
            by_relation_type[relation_type] = by_relation_type.get(relation_type, 0) + 1

            target_type = s.get("target_type", "node")
            by_target_type[target_type] = by_target_type.get(target_type, 0) + 1

            total_confidence += s.get("confidence", 0.0)
            total_strength += s.get("strength", 0.0)

        count = len(suggestions)
        avg_confidence = total_confidence / count if count > 0 else 0.0
        avg_strength = total_strength / count if count > 0 else 0.0

        # Get last analysis time
        last_analysis = None
        for batch_info in self._index.get("batches", {}).values():
            analyzed_at = batch_info.get("analyzed_at")
            if analyzed_at:
                analyzed_dt = datetime.fromisoformat(analyzed_at)
                if last_analysis is None or analyzed_dt > last_analysis:
                    last_analysis = analyzed_dt

        return RelationshipStats(
            total_suggestions=stats.get("total", 0),
            pending_count=stats.get("pending", 0),
            confirmed_count=stats.get("confirmed", 0),
            rejected_count=stats.get("rejected", 0),
            by_relation_type=by_relation_type,
            by_target_type=by_target_type,
            average_confidence=avg_confidence,
            average_strength=avg_strength,
            last_analysis_at=last_analysis,
        )

    def get_all_suggestions(
        self,
        status: Optional[SuggestionStatus] = None,
    ) -> list[RelationshipSuggestion]:
        """Get all suggestions.

        Args:
            status: Optional filter by status

        Returns:
            List of all suggestions
        """
        suggestions = []
        for suggestion_info in self._index["suggestions"].values():
            if status is None or suggestion_info["status"] == status.value:
                suggestion = self.get_suggestion(suggestion_info["id"])
                if suggestion:
                    suggestions.append(suggestion)

        return suggestions

    def has_pending_suggestions(self, node_id: str) -> bool:
        """Check if a node has pending suggestions.

        Args:
            node_id: The node ID

        Returns:
            True if there are pending suggestions
        """
        for suggestion_info in self._index["suggestions"].values():
            if (
                suggestion_info["source_id"] == node_id
                and suggestion_info["status"] == SuggestionStatus.PENDING.value
            ):
                return True
        return False
