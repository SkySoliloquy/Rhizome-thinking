"""Theme evolution API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from rhizome.core.theme_models import Theme
from rhizome.core.theme_store import ThemeStore
from rhizome.core.theme_evolution import (
    ThemeEvolutionAnalyzer,
    MockThemeEvolutionAnalyzer,
    ThemeEvolutionSuggestion,
    ConflictType,
    SuggestionStatus
)
from rhizome.core.evolution_store import EvolutionStore
from rhizome.core.node_store import NodeStore
from rhizome.config import settings

router = APIRouter()


class ThemeEvolutionHistoryResponse(BaseModel):
    """Theme evolution history response."""
    theme_id: str
    current_version: int
    evolution_status: str
    history: list[dict]


class EvolutionSuggestionResponse(BaseModel):
    """Evolution suggestion response."""
    id: str
    theme_id: str
    suggested_summary: Optional[str]
    suggested_tag: Optional[str]
    conflict_type: str
    reason: str
    affected_node_ids: list[str]
    status: str
    created_at: str
    applied_at: Optional[str]
    previous_version: Optional[int]


class PendingSuggestionsResponse(BaseModel):
    """Pending suggestions list response."""
    total: int
    suggestions: list[EvolutionSuggestionResponse]


class ConflictDetectionResponse(BaseModel):
    """Conflict detection response."""
    theme_id: str
    conflicts: list[EvolutionSuggestionResponse]
    total_conflicts: int


class ApplySuggestionRequest(BaseModel):
    """Request to apply a suggestion."""
    confirm: bool = Field(default=True, description="Confirm the application")


class ApplySuggestionResponse(BaseModel):
    """Apply suggestion response."""
    success: bool
    message: str
    theme_id: Optional[str]
    new_version: Optional[int]


class RejectSuggestionRequest(BaseModel):
    """Request to reject a suggestion."""
    reason: Optional[str] = Field(default=None, description="Reason for rejection")


class RejectSuggestionResponse(BaseModel):
    """Reject suggestion response."""
    success: bool
    message: str


class RollbackRequest(BaseModel):
    """Request to rollback theme version."""
    confirm: bool = Field(default=True, description="Confirm the rollback")


class RollbackResponse(BaseModel):
    """Rollback response."""
    success: bool
    message: str
    theme_id: str
    rolled_to_version: int
    previous_version: int


class AnalyzeThemeRequest(BaseModel):
    """Request to analyze theme evolution."""
    include_nodes: bool = Field(default=True, description="Include related nodes in analysis")


class AnalyzeThemeResponse(BaseModel):
    """Analyze theme response."""
    success: bool
    message: str
    theme_id: str
    suggestions_generated: int
    suggestions: list[EvolutionSuggestionResponse]


def _get_analyzer() -> ThemeEvolutionAnalyzer:
    """Get theme evolution analyzer instance."""
    try:
        return ThemeEvolutionAnalyzer(theme_store=ThemeStore())
    except ValueError:
        return MockThemeEvolutionAnalyzer(theme_store=ThemeStore())


def _convert_suggestion_to_response(suggestion: ThemeEvolutionSuggestion) -> EvolutionSuggestionResponse:
    """Convert ThemeEvolutionSuggestion to response model."""
    return EvolutionSuggestionResponse(
        id=suggestion.id,
        theme_id=suggestion.theme_id,
        suggested_summary=suggestion.suggested_summary,
        suggested_tag=suggestion.suggested_tag,
        conflict_type=suggestion.conflict_type.value,
        reason=suggestion.reason,
        affected_node_ids=suggestion.affected_node_ids,
        status=suggestion.status.value,
        created_at=suggestion.created_at.isoformat() if suggestion.created_at else "",
        applied_at=suggestion.applied_at.isoformat() if suggestion.applied_at else None,
        previous_version=suggestion.previous_version
    )


@router.get("/themes/{theme_id}/evolution", response_model=ThemeEvolutionHistoryResponse)
async def get_theme_evolution(
    theme_id: str
):
    """Get theme evolution history.

    Returns the version history and evolution status of a theme.
    """
    theme_store = ThemeStore()
    theme = theme_store.get_theme(theme_id)

    if not theme:
        raise HTTPException(status_code=404, detail="主题不存在")

    history = []
    for version in theme.evolution_history:
        history.append({
            "version": version.version,
            "summary": version.summary,
            "tag": version.tag,
            "updated_at": version.updated_at.isoformat() if version.updated_at else "",
            "reason": version.reason
        })

    return ThemeEvolutionHistoryResponse(
        theme_id=theme.id,
        current_version=theme.version,
        evolution_status=theme.evolution_status,
        history=history
    )


@router.get("/themes/evolution/suggestions", response_model=PendingSuggestionsResponse)
async def list_pending_suggestions(
    status: Optional[str] = Query(default="pending", description="Filter by status: pending, applied, rejected, rolled_back"),
    theme_id: Optional[str] = Query(default=None, description="Filter by theme ID"),
    limit: int = Query(default=50, ge=1, le=200)
):
    """List evolution suggestions.

    Returns a list of evolution suggestions filtered by status and/or theme.
    """
    store = EvolutionStore()

    if theme_id:
        suggestions = store.get_suggestions_for_theme(theme_id)
        if status:
            try:
                target_status = SuggestionStatus(status)
                suggestions = [s for s in suggestions if s.status == target_status]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的状态值: {status}")
    else:
        if status:
            try:
                target_status = SuggestionStatus(status)
                suggestions = store.get_suggestions_by_status(target_status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的状态值: {status}")
        else:
            suggestions = store.get_all_suggestions()

    suggestions = suggestions[:limit]

    return PendingSuggestionsResponse(
        total=len(suggestions),
        suggestions=[_convert_suggestion_to_response(s) for s in suggestions]
    )


@router.post("/themes/evolution/suggestions/{suggestion_id}/apply", response_model=ApplySuggestionResponse)
async def apply_suggestion(
    suggestion_id: str,
    request: Optional[ApplySuggestionRequest] = None
):
    """Apply an evolution suggestion.

    Applies the suggested changes to the target theme and updates the suggestion status.
    """
    store = EvolutionStore()
    suggestion = store.get_suggestion(suggestion_id)

    if not suggestion:
        raise HTTPException(status_code=404, detail="演进建议不存在")

    if suggestion.status != SuggestionStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"建议状态不是待处理(当前状态: {suggestion.status.value})"
        )

    analyzer = _get_analyzer()

    try:
        success = await analyzer.apply_evolution(suggestion_id)

        if success:
            theme_store = ThemeStore()
            theme = theme_store.get_theme(suggestion.theme_id)
            return ApplySuggestionResponse(
                success=True,
                message="演进建议已成功应用",
                theme_id=suggestion.theme_id,
                new_version=theme.version if theme else None
            )
        else:
            raise HTTPException(status_code=500, detail="应用演进建议失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"应用演进建议时出错: {str(e)}")


@router.post("/themes/evolution/suggestions/{suggestion_id}/reject", response_model=RejectSuggestionResponse)
async def reject_suggestion(
    suggestion_id: str,
    request: Optional[RejectSuggestionRequest] = None
):
    """Reject an evolution suggestion.

    Marks the suggestion as rejected without applying any changes.
    """
    store = EvolutionStore()
    suggestion = store.get_suggestion(suggestion_id)

    if not suggestion:
        raise HTTPException(status_code=404, detail="演进建议不存在")

    if suggestion.status != SuggestionStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"只能拒绝待处理状态的建议(当前状态: {suggestion.status.value})"
        )

    success = store.update_suggestion_status(suggestion_id, SuggestionStatus.REJECTED)

    if success:
        return RejectSuggestionResponse(
            success=True,
            message="演进建议已拒绝"
        )
    else:
        raise HTTPException(status_code=500, detail="拒绝演进建议失败")


@router.post("/themes/{theme_id}/rollback/{version}", response_model=RollbackResponse)
async def rollback_theme(
    theme_id: str,
    version: int,
    request: Optional[RollbackRequest] = None
):
    """Rollback theme to specific version.

    Restores the theme to a previous version from its evolution history.
    """
    theme_store = ThemeStore()
    theme = theme_store.get_theme(theme_id)

    if not theme:
        raise HTTPException(status_code=404, detail="主题不存在")

    target_version = None
    for v in theme.evolution_history:
        if v.version == version:
            target_version = v
            break

    if not target_version:
        raise HTTPException(status_code=404, detail=f"版本 {version} 不存在于主题历史中")

    current_version = theme.version

    analyzer = _get_analyzer()

    try:
        success = await analyzer.rollback_evolution(theme_id, version)

        if success:
            return RollbackResponse(
                success=True,
                message=f"主题已成功回滚到版本 {version}",
                theme_id=theme_id,
                rolled_to_version=version,
                previous_version=current_version
            )
        else:
            raise HTTPException(status_code=500, detail="回滚主题失败")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回滚主题时出错: {str(e)}")


@router.get("/themes/{theme_id}/conflicts", response_model=ConflictDetectionResponse)
async def detect_theme_conflicts(
    theme_id: str
):
    """Detect conflicts for a theme.

    Analyzes the theme and its related nodes to identify potential conflicts.
    """
    theme_store = ThemeStore()
    node_store = NodeStore()
    store = EvolutionStore()

    theme = theme_store.get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="主题不存在")

    # Get existing suggestions for this theme
    suggestions = store.get_suggestions_for_theme(theme_id)
    pending_suggestions = [s for s in suggestions if s.status == SuggestionStatus.PENDING]

    return ConflictDetectionResponse(
        theme_id=theme_id,
        conflicts=[_convert_suggestion_to_response(s) for s in pending_suggestions],
        total_conflicts=len(pending_suggestions)
    )


@router.post("/themes/{theme_id}/analyze", response_model=AnalyzeThemeResponse)
async def analyze_theme_evolution(
    theme_id: str,
    request: Optional[AnalyzeThemeRequest] = None
):
    """Trigger manual evolution analysis.

    Analyzes a theme and generates evolution suggestions based on its related nodes.
    """
    theme_store = ThemeStore()
    node_store = NodeStore()
    store = EvolutionStore()

    theme = theme_store.get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="主题不存在")

    # Get related nodes
    related_nodes = []
    if request is None or request.include_nodes:
        for node_id in theme.node_ids:
            node = node_store.get(node_id)
            if node:
                related_nodes.append(node)

    if not related_nodes:
        raise HTTPException(status_code=400, detail="主题没有关联的笔记，无法进行分析")

    analyzer = _get_analyzer()

    try:
        # Generate evolution suggestions
        suggestions = await analyzer.generate_evolution_suggestions(theme, related_nodes)

        # Save suggestions
        for suggestion in suggestions:
            store.save_suggestion(suggestion)

        return AnalyzeThemeResponse(
            success=True,
            message=f"主题演进分析完成，生成了 {len(suggestions)} 条建议",
            theme_id=theme_id,
            suggestions_generated=len(suggestions),
            suggestions=[_convert_suggestion_to_response(s) for s in suggestions]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析主题演进时出错: {str(e)}")
