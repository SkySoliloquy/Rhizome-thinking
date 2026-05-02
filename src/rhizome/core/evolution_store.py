"""Evolution suggestion storage management for Rhizome Thinking."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rhizome.config import settings
from rhizome.core.theme_evolution import SuggestionStatus, ThemeEvolutionSuggestion


class EvolutionStore:
    """Manages storage and retrieval of theme evolution suggestions."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """Initialize the evolution store.

        Args:
            storage_dir: Override the default storage directory
        """
        self.storage_dir = storage_dir or settings.storage_dir
        self.suggestions_dir = self.storage_dir / "metadata" / "evolution_suggestions"
        self.index_path = self.storage_dir / "metadata" / "evolution_index.json"

        # Ensure directories exist
        self._ensure_directories()

        # Load or create index
        self._index = self._load_index()

    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.suggestions_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict:
        """Load the evolution suggestions index from disk."""
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "suggestions": {},
            "by_theme": {},
            "by_status": {
                "pending": [],
                "applied": [],
                "rejected": [],
                "rolled_back": []
            },
            "last_updated": datetime.now().isoformat()
        }

    def _save_index(self) -> None:
        """Save the evolution suggestions index to disk."""
        self._index["last_updated"] = datetime.now().isoformat()
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _get_suggestion_path(self, suggestion_id: str) -> Path:
        """Get the file path for a suggestion."""
        return self.suggestions_dir / f"{suggestion_id}.json"

    def save_suggestion(self, suggestion: ThemeEvolutionSuggestion) -> None:
        """Save an evolution suggestion to storage.

        Args:
            suggestion: The suggestion to save
        """
        suggestion_path = self._get_suggestion_path(suggestion.id)
        with open(suggestion_path, "w", encoding="utf-8") as f:
            json.dump(suggestion.model_dump(), f, indent=2, ensure_ascii=False)

        # Update index
        self._index["suggestions"][suggestion.id] = {
            "id": suggestion.id,
            "theme_id": suggestion.theme_id,
            "conflict_type": suggestion.conflict_type.value,
            "status": suggestion.status.value,
            "created_at": suggestion.created_at.isoformat(),
            "reason": suggestion.reason[:200]  # Truncate for index
        }

        # Update by_theme index
        if suggestion.theme_id not in self._index["by_theme"]:
            self._index["by_theme"][suggestion.theme_id] = []
        if suggestion.id not in self._index["by_theme"][suggestion.theme_id]:
            self._index["by_theme"][suggestion.theme_id].append(suggestion.id)

        # Update by_status index
        for status_list in self._index["by_status"].values():
            if suggestion.id in status_list:
                status_list.remove(suggestion.id)

        status_key = suggestion.status.value
        if status_key in self._index["by_status"]:
            if suggestion.id not in self._index["by_status"][status_key]:
                self._index["by_status"][status_key].append(suggestion.id)

        self._save_index()

    def get_suggestion(self, suggestion_id: str) -> Optional[ThemeEvolutionSuggestion]:
        """Retrieve an evolution suggestion by ID.

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

        return ThemeEvolutionSuggestion(**data)

    def delete_suggestion(self, suggestion_id: str) -> bool:
        """Delete an evolution suggestion.

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

        # Get suggestion info for index cleanup
        suggestion_info = self._index["suggestions"].get(suggestion_id, {})
        theme_id = suggestion_info.get("theme_id")

        # Update index
        if suggestion_id in self._index["suggestions"]:
            del self._index["suggestions"][suggestion_id]

        # Remove from by_theme index
        if theme_id and theme_id in self._index["by_theme"]:
            if suggestion_id in self._index["by_theme"][theme_id]:
                self._index["by_theme"][theme_id].remove(suggestion_id)
            if not self._index["by_theme"][theme_id]:
                del self._index["by_theme"][theme_id]

        # Remove from by_status index
        for status_list in self._index["by_status"].values():
            if suggestion_id in status_list:
                status_list.remove(suggestion_id)

        self._save_index()
        return True

    def get_suggestions_for_theme(self, theme_id: str) -> list[ThemeEvolutionSuggestion]:
        """Get all evolution suggestions for a specific theme.

        Args:
            theme_id: The theme ID

        Returns:
            List of suggestions for the theme
        """
        suggestion_ids = self._index["by_theme"].get(theme_id, [])
        suggestions = []

        for sid in suggestion_ids:
            suggestion = self.get_suggestion(sid)
            if suggestion:
                suggestions.append(suggestion)

        # Sort by creation time (newest first)
        suggestions.sort(key=lambda s: s.created_at, reverse=True)
        return suggestions

    def get_suggestions_by_status(self, status: SuggestionStatus) -> list[ThemeEvolutionSuggestion]:
        """Get all evolution suggestions with a specific status.

        Args:
            status: The status to filter by

        Returns:
            List of suggestions with the specified status
        """
        suggestion_ids = self._index["by_status"].get(status.value, [])
        suggestions = []

        for sid in suggestion_ids:
            suggestion = self.get_suggestion(sid)
            if suggestion:
                suggestions.append(suggestion)

        # Sort by creation time (newest first)
        suggestions.sort(key=lambda s: s.created_at, reverse=True)
        return suggestions

    def get_all_suggestions(self) -> list[ThemeEvolutionSuggestion]:
        """Get all evolution suggestions.

        Returns:
            List of all suggestions
        """
        suggestions = []
        for suggestion_id in self._index["suggestions"].keys():
            suggestion = self.get_suggestion(suggestion_id)
            if suggestion:
                suggestions.append(suggestion)

        # Sort by creation time (newest first)
        suggestions.sort(key=lambda s: s.created_at, reverse=True)
        return suggestions

    def get_pending_suggestions(self) -> list[ThemeEvolutionSuggestion]:
        """Get all pending evolution suggestions.

        Returns:
            List of pending suggestions
        """
        return self.get_suggestions_by_status(SuggestionStatus.PENDING)

    def update_suggestion_status(
        self,
        suggestion_id: str,
        new_status: SuggestionStatus
    ) -> bool:
        """Update the status of an evolution suggestion.

        Args:
            suggestion_id: The suggestion ID
            new_status: The new status to set

        Returns:
            True if successful
        """
        suggestion = self.get_suggestion(suggestion_id)
        if not suggestion:
            return False

        # Remove from old status list
        old_status = suggestion.status.value
        if old_status in self._index["by_status"]:
            if suggestion_id in self._index["by_status"][old_status]:
                self._index["by_status"][old_status].remove(suggestion_id)

        # Update suggestion
        suggestion.status = new_status
        if new_status == SuggestionStatus.APPLIED:
            suggestion.applied_at = datetime.now()

        # Save
        self.save_suggestion(suggestion)
        return True

    def get_stats(self) -> dict:
        """Get statistics about stored evolution suggestions.

        Returns:
            Dictionary with statistics
        """
        total = len(self._index["suggestions"])

        # Count by status
        status_counts = {}
        for status, ids in self._index["by_status"].items():
            status_counts[status] = len(ids)

        # Count by conflict type
        type_counts = {}
        for suggestion_info in self._index["suggestions"].values():
            conflict_type = suggestion_info.get("conflict_type", "unknown")
            type_counts[conflict_type] = type_counts.get(conflict_type, 0) + 1

        # Count by theme
        theme_counts = {}
        for theme_id, suggestion_ids in self._index["by_theme"].items():
            theme_counts[theme_id] = len(suggestion_ids)

        return {
            "total_suggestions": total,
            "status_distribution": status_counts,
            "conflict_type_distribution": type_counts,
            "themes_with_suggestions": len(theme_counts),
            "last_updated": self._index.get("last_updated")
        }

    def cleanup_old_suggestions(self, days: int = 30) -> int:
        """Clean up old rejected or rolled back suggestions.

        Args:
            days: Number of days after which to clean up old suggestions

        Returns:
            Number of suggestions cleaned up
        """
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        to_delete = []

        for suggestion_id, info in self._index["suggestions"].items():
            status = info.get("status")
            if status in ["rejected", "rolled_back"]:
                created_at = info.get("created_at", "")
                try:
                    created_ts = datetime.fromisoformat(created_at).timestamp()
                    if created_ts < cutoff:
                        to_delete.append(suggestion_id)
                except (ValueError, TypeError):
                    continue

        deleted_count = 0
        for suggestion_id in to_delete:
            if self.delete_suggestion(suggestion_id):
                deleted_count += 1

        return deleted_count
