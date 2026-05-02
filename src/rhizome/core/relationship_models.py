"""Relationship suggestion models for Rhizome Thinking."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_serializer


RelationType = Literal["support", "contradict", "extend", "source", "analogy"]
TargetType = Literal["node", "theme"]


class SuggestionStatus(str, Enum):
    """Status of a relationship suggestion."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class RelationshipSuggestion(BaseModel):
    """AI-generated suggestion for a relationship between entities."""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Suggestion unique identifier"
    )
    source_id: str = Field(
        ...,
        description="ID of the source node"
    )
    target_id: str = Field(
        ...,
        description="ID of the target node or theme"
    )
    target_type: TargetType = Field(
        default="node",
        description="Type of the target: node or theme"
    )
    relation_type: RelationType = Field(
        ...,
        description="Type of relationship"
    )
    strength: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relationship strength (0.0 - 1.0)"
    )
    reason: str = Field(
        default="",
        description="AI-generated explanation for this relationship"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="AI confidence in this suggestion (0.0 - 1.0)"
    )
    status: SuggestionStatus = Field(
        default=SuggestionStatus.PENDING,
        description="Current status of the suggestion"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this suggestion was created"
    )
    reviewed_at: Optional[datetime] = Field(
        default=None,
        description="When this suggestion was reviewed"
    )
    reviewed_by: Optional[str] = Field(
        default=None,
        description="Who reviewed this suggestion (user or system)"
    )
    source_proposition: str = Field(
        default="",
        description="Cached source node proposition for display"
    )
    target_proposition: str = Field(
        default="",
        description="Cached target node/theme summary for display"
    )
    
    @field_serializer("created_at", "reviewed_at")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None
    
    @field_serializer("status")
    def serialize_status(self, value: SuggestionStatus) -> str:
        return value.value
    
    def confirm(self, reviewed_by: str = "user") -> None:
        """Confirm this suggestion."""
        self.status = SuggestionStatus.CONFIRMED
        self.reviewed_at = datetime.now()
        self.reviewed_by = reviewed_by
    
    def reject(self, reviewed_by: str = "user") -> None:
        """Reject this suggestion."""
        self.status = SuggestionStatus.REJECTED
        self.reviewed_at = datetime.now()
        self.reviewed_by = reviewed_by
    
    def to_link_dict(self) -> dict:
        """Convert to a Link-compatible dictionary."""
        return {
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "strength": self.strength,
            "confirmed": True,
            "auto_confirmed": False,
            "reason": self.reason
        }
    
    def __str__(self) -> str:
        status_symbol = {
            SuggestionStatus.PENDING: "?",
            SuggestionStatus.CONFIRMED: "✓",
            SuggestionStatus.REJECTED: "✗"
        }
        return f"[{status_symbol[self.status]}] {self.source_id[:8]} --{self.relation_type}--> {self.target_id[:8]} ({self.confidence:.2f})"


class RelationshipBatch(BaseModel):
    """Batch of relationship suggestions for a node."""
    
    node_id: str = Field(
        ...,
        description="ID of the source node"
    )
    suggestions: list[RelationshipSuggestion] = Field(
        default_factory=list,
        description="List of relationship suggestions"
    )
    analyzed_at: datetime = Field(
        default_factory=datetime.now,
        description="When this batch was analyzed"
    )
    analysis_version: str = Field(
        default="1.0",
        description="Version of the analysis algorithm"
    )
    
    @field_serializer("analyzed_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
    
    @property
    def pending_count(self) -> int:
        """Get number of pending suggestions."""
        return sum(1 for s in self.suggestions if s.status == SuggestionStatus.PENDING)
    
    @property
    def confirmed_count(self) -> int:
        """Get number of confirmed suggestions."""
        return sum(1 for s in self.suggestions if s.status == SuggestionStatus.CONFIRMED)
    
    @property
    def rejected_count(self) -> int:
        """Get number of rejected suggestions."""
        return sum(1 for s in self.suggestions if s.status == SuggestionStatus.REJECTED)


class RelationshipStats(BaseModel):
    """Statistics for relationship suggestions."""
    
    total_suggestions: int = Field(default=0)
    pending_count: int = Field(default=0)
    confirmed_count: int = Field(default=0)
    rejected_count: int = Field(default=0)
    by_relation_type: dict[str, int] = Field(default_factory=dict)
    by_target_type: dict[str, int] = Field(default_factory=dict)
    average_confidence: float = Field(default=0.0)
    average_strength: float = Field(default=0.0)
    last_analysis_at: Optional[datetime] = Field(default=None)
    
    @field_serializer("last_analysis_at")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None
