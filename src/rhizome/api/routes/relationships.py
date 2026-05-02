"""Relationship management API routes for Rhizome Thinking."""

from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from rhizome.core.node_store import NodeStore
from rhizome.core.relationship_manager import RelationshipManager
from rhizome.core.relationship_store import RelationshipStore
from rhizome.core.relationship_models import (
    RelationshipStats,
    RelationshipSuggestion,
    SuggestionStatus,
)
from rhizome.api.dependencies import get_node_store

router = APIRouter()

# Singleton instances
_relationship_manager: RelationshipManager | None = None
_relationship_store: RelationshipStore | None = None


def _get_relationship_manager_singleton() -> RelationshipManager:
    """Get or create RelationshipManager singleton."""
    global _relationship_manager
    if _relationship_manager is None:
        _relationship_manager = RelationshipManager()
    return _relationship_manager


def _get_relationship_store_singleton() -> RelationshipStore:
    """Get or create RelationshipStore singleton."""
    global _relationship_store
    if _relationship_store is None:
        _relationship_store = RelationshipStore()
    return _relationship_store


async def get_relationship_manager() -> AsyncGenerator[RelationshipManager, None]:
    """Dependency for RelationshipManager."""
    yield _get_relationship_manager_singleton()


async def get_relationship_store() -> AsyncGenerator[RelationshipStore, None]:
    """Dependency for RelationshipStore."""
    yield _get_relationship_store_singleton()


class SuggestionResponse(BaseModel):
    """Response model for a relationship suggestion."""
    id: str
    source_id: str
    target_id: str
    target_type: str
    relation_type: str
    relation_name: str
    strength: float
    confidence: float
    reason: str
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    source_proposition: str
    target_proposition: str


class SuggestionsListResponse(BaseModel):
    """Response model for paginated suggestions list."""
    suggestions: list[SuggestionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class NodeRelationshipsResponse(BaseModel):
    """Response model for node relationships."""
    node_id: str
    outgoing: list[dict]
    incoming: list[dict]
    suggestions: list[SuggestionResponse]
    total_outgoing: int
    total_incoming: int
    total_suggestions: int


class AnalyzeRequest(BaseModel):
    """Request model for manual analysis."""
    max_candidates: int = Field(default=20, ge=5, le=50, description="最大候选节点数")


class AnalyzeResponse(BaseModel):
    """Response model for analysis result."""
    message: str
    node_id: str
    suggestions_count: int
    suggestions: list[SuggestionResponse]


class ConfirmRejectResponse(BaseModel):
    """Response model for confirm/reject actions."""
    message: str
    suggestion_id: str
    status: str


class StatsResponse(BaseModel):
    """Response model for relationship statistics."""
    total_suggestions: int
    pending_count: int
    confirmed_count: int
    rejected_count: int
    by_relation_type: dict[str, int]
    by_target_type: dict[str, int]
    average_confidence: float
    average_strength: float
    last_analysis_at: Optional[str]


RELATION_TYPE_NAMES = {
    "support": "支持",
    "contradict": "矛盾",
    "extend": "延伸",
    "source": "来源",
    "analogy": "类比",
}

STATUS_NAMES = {
    "pending": "待处理",
    "confirmed": "已确认",
    "rejected": "已拒绝",
}


def _suggestion_to_response(suggestion: RelationshipSuggestion) -> SuggestionResponse:
    """Convert RelationshipSuggestion to response model."""
    return SuggestionResponse(
        id=suggestion.id,
        source_id=suggestion.source_id,
        target_id=suggestion.target_id,
        target_type=suggestion.target_type,
        relation_type=suggestion.relation_type,
        relation_name=RELATION_TYPE_NAMES.get(suggestion.relation_type, suggestion.relation_type),
        strength=suggestion.strength,
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        status=suggestion.status.value,
        created_at=suggestion.created_at.isoformat(),
        reviewed_at=suggestion.reviewed_at.isoformat() if suggestion.reviewed_at else None,
        source_proposition=suggestion.source_proposition,
        target_proposition=suggestion.target_proposition,
    )


@router.get("/relationships/suggestions", response_model=SuggestionsListResponse)
async def list_suggestions(
    status: Optional[str] = Query(default=None, description="筛选状态: pending, confirmed, rejected"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    store: RelationshipStore = Depends(get_relationship_store),
):
    """获取关系建议列表（支持分页）。"""
    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = SuggestionStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的状态值: {status}。有效值: pending, confirmed, rejected"
            )

    # Get all suggestions with filter
    all_suggestions = store.get_all_suggestions(status=status_filter)

    # Calculate pagination
    total = len(all_suggestions)
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_suggestions = all_suggestions[start_idx:end_idx]

    return SuggestionsListResponse(
        suggestions=[_suggestion_to_response(s) for s in paginated_suggestions],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/relationships/suggestions/{suggestion_id}/confirm", response_model=ConfirmRejectResponse)
async def confirm_suggestion(
    suggestion_id: str,
    manager: RelationshipManager = Depends(get_relationship_manager),
    store: RelationshipStore = Depends(get_relationship_store),
):
    """确认一个关系建议。"""
    # Check if suggestion exists
    suggestion = store.get_suggestion(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="建议未找到")

    # Confirm the suggestion
    success = manager.apply_suggestion(suggestion_id)
    if not success:
        raise HTTPException(status_code=400, detail="确认建议失败")

    return ConfirmRejectResponse(
        message="建议已确认",
        suggestion_id=suggestion_id,
        status="confirmed",
    )


@router.post("/relationships/suggestions/{suggestion_id}/reject", response_model=ConfirmRejectResponse)
async def reject_suggestion(
    suggestion_id: str,
    manager: RelationshipManager = Depends(get_relationship_manager),
    store: RelationshipStore = Depends(get_relationship_store),
):
    """拒绝一个关系建议。"""
    # Check if suggestion exists
    suggestion = store.get_suggestion(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="建议未找到")

    # Reject the suggestion
    success = manager.reject_suggestion(suggestion_id)
    if not success:
        raise HTTPException(status_code=400, detail="拒绝建议失败")

    return ConfirmRejectResponse(
        message="建议已拒绝",
        suggestion_id=suggestion_id,
        status="rejected",
    )


@router.get("/relationships/node/{node_id}", response_model=NodeRelationshipsResponse)
async def get_node_relationships(
    node_id: str,
    include_suggestions: bool = Query(default=True, description="是否包含建议"),
    node_store: NodeStore = Depends(get_node_store),
    rel_store: RelationshipStore = Depends(get_relationship_store),
):
    """获取节点的所有关系（出向、入向和建议）。"""
    # Check if node exists
    node = node_store.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点未找到")

    # Get outgoing links from the node itself
    outgoing = []
    for link in node.links:
        target = node_store.get(link.target_id)
        outgoing.append({
            "target_id": link.target_id,
            "target_proposition": target.processed.proposition if target else "未知节点",
            "relation_type": link.relation_type,
            "relation_name": RELATION_TYPE_NAMES.get(link.relation_type, link.relation_type),
            "strength": link.strength,
            "confirmed": link.confirmed,
        })

    # Get incoming links from other nodes
    incoming = []
    all_nodes = node_store.list_all()
    for other_node in all_nodes:
        if other_node.id == node_id:
            continue
        for link in other_node.links:
            if link.target_id == node_id:
                incoming.append({
                    "source_id": other_node.id,
                    "source_proposition": other_node.processed.proposition,
                    "relation_type": link.relation_type,
                    "relation_name": RELATION_TYPE_NAMES.get(link.relation_type, link.relation_type),
                    "strength": link.strength,
                    "confirmed": link.confirmed,
                })

    # Get suggestions for this node
    suggestions = []
    if include_suggestions:
        node_suggestions = rel_store.get_suggestions_for_node(node_id)
        suggestions = [_suggestion_to_response(s) for s in node_suggestions]

    return NodeRelationshipsResponse(
        node_id=node_id,
        outgoing=outgoing,
        incoming=incoming,
        suggestions=suggestions,
        total_outgoing=len(outgoing),
        total_incoming=len(incoming),
        total_suggestions=len(suggestions),
    )


@router.post("/relationships/analyze", response_model=AnalyzeResponse)
async def analyze_node(
    node_id: str,
    request: Optional[AnalyzeRequest] = None,
    manager: RelationshipManager = Depends(get_relationship_manager),
    node_store: NodeStore = Depends(get_node_store),
):
    """手动触发节点的关系分析。"""
    # Check if node exists
    node = node_store.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点未找到")

    # Get all other nodes as candidates
    all_nodes = node_store.list_all()
    other_nodes = [n for n in all_nodes if n.id != node_id]

    if not other_nodes:
        return AnalyzeResponse(
            message="没有其他节点可供分析",
            node_id=node_id,
            suggestions_count=0,
            suggestions=[],
        )

    # Perform analysis
    max_candidates = request.max_candidates if request else 20
    try:
        suggestions = await manager.analyze_new_node(
            node=node,
            all_nodes=other_nodes,
            all_themes=[],  # TODO: Load themes if needed
            max_candidates=max_candidates,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")

    return AnalyzeResponse(
        message=f"分析完成，发现 {len(suggestions)} 个潜在关系",
        node_id=node_id,
        suggestions_count=len(suggestions),
        suggestions=[_suggestion_to_response(s) for s in suggestions],
    )


@router.get("/relationships/stats", response_model=StatsResponse)
async def get_relationship_stats(
    store: RelationshipStore = Depends(get_relationship_store),
) -> StatsResponse:
    """获取关系建议的统计数据。"""
    stats = store.get_stats()
    return StatsResponse(
        total_suggestions=stats.total_suggestions,
        pending_count=stats.pending_count,
        confirmed_count=stats.confirmed_count,
        rejected_count=stats.rejected_count,
        by_relation_type=stats.by_relation_type,
        by_target_type=stats.by_target_type,
        average_confidence=stats.average_confidence,
        average_strength=stats.average_strength,
        last_analysis_at=stats.last_analysis_at.isoformat() if stats.last_analysis_at else None,
    )
