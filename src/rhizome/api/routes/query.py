"""Query API routes for semantic search."""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rhizome.retrieval.query_engine import QueryEngine, QueryModifiers, QueryResult
from rhizome.api.dependencies import get_query_engine
from rhizome.core.node_store import NodeStore
from rhizome.api.dependencies import get_node_store

router = APIRouter()


class QueryRequest(BaseModel):
    """Semantic query request."""
    anchor: str = Field(..., min_length=1, description="语义锚点 - 查询的核心内容")
    modifiers: QueryModifiers = Field(
        default_factory=QueryModifiers,
        description="查询修饰符 - 用于过滤结果"
    )


class PreciseQueryRequest(BaseModel):
    """Precise query request (distinct from semantic search)."""
    search_mode: Literal["semantic", "precise"] = "precise"
    proposition_query: Optional[str] = Field(default=None, description="命题关键字")
    raw_content_query: Optional[str] = Field(default=None, description="原始内容关键字")
    start_date: Optional[datetime] = Field(default=None, description="开始日期")
    end_date: Optional[datetime] = Field(default=None, description="结束日期")
    tags: list[str] = Field(default_factory=list, description="标签筛选")
    sort_by: Literal["time", "proposition"] = "time"
    limit: int = Field(default=50, ge=1, le=200, description="最大结果数")


class PreciseQueryResultItem(BaseModel):
    """Single precise query result item."""
    id: str
    proposition: str
    raw_input: str
    refined_content: Optional[str] = None
    has_refined_content: bool = False
    tags: list[str]
    timestamp: str
    source_title: Optional[str] = None
    source_location: Optional[str] = None


class PreciseQueryResponse(BaseModel):
    """Precise query response."""
    results: list[PreciseQueryResultItem]
    total: int
    query: dict


class QueryResultItem(BaseModel):
    """Single query result item."""
    id: str
    proposition: str
    refined_content: Optional[str] = None
    has_refined_content: bool = False
    tags: list[str]
    timestamp: str
    similarity: float
    highlight: str


class QueryResponse(BaseModel):
    """Query response."""
    results: list[QueryResultItem]
    grouped_by_tag: dict[str, list[QueryResultItem]]
    total: int
    query: str


class ClusterViewResponse(BaseModel):
    """Cluster view response - grouped by tags."""
    clusters: dict[str, list[QueryResultItem]]
    query: str
    total: int


def _convert_result_to_item(result: QueryResult) -> QueryResultItem:
    """Convert QueryResult to QueryResultItem."""
    # Prioritize refined_content: use node.refined_content if available,
    # otherwise fall back to processed.refined_content
    refined = result.node.refined_content or result.node.processed.refined_content or None
    return QueryResultItem(
        id=result.node.id,
        proposition=result.node.processed.proposition,
        refined_content=refined,
        has_refined_content=bool(refined),
        tags=result.node.tags,
        timestamp=result.node.timestamp.isoformat(),
        similarity=round(result.similarity, 2),
        highlight=result.highlight or ""
    )


@router.post("/query", response_model=QueryResponse)
async def semantic_query(
    request: QueryRequest,
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Execute semantic query with two-stage search.
    
    阶段1: 向量语义检索
    阶段2: 根据修饰符过滤和分组
    """
    try:
        # Execute search
        results = await query_engine.search(
            anchor=request.anchor,
            modifiers=request.modifiers
        )
        
        # Convert to response items
        result_items = [_convert_result_to_item(r) for r in results]
        
        # Group by tags
        grouped = query_engine.group_by_tags(results)
        grouped_items = {
            tag: [_convert_result_to_item(r) for r in items]
            for tag, items in grouped.items()
        }
        
        return QueryResponse(
            results=result_items,
            grouped_by_tag=grouped_items,
            total=len(result_items),
            query=request.anchor
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/query/cluster", response_model=ClusterViewResponse)
async def cluster_view_query(
    request: QueryRequest,
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Get query results in cluster view format (grouped by tags).
    
    适合场景: 快速了解在某个主题下自己有哪些类型的积累
    """
    try:
        # Execute search
        results = await query_engine.search(
            anchor=request.anchor,
            modifiers=request.modifiers
        )
        
        # Group by tags
        grouped = query_engine.group_by_tags(results)
        grouped_items = {
            tag: [_convert_result_to_item(r) for r in items]
            for tag, items in grouped.items()
        }
        
        return ClusterViewResponse(
            clusters=grouped_items,
            query=request.anchor,
            total=len(results)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/query/precise", response_model=PreciseQueryResponse)
async def precise_query(
    request: PreciseQueryRequest,
    node_store: NodeStore = Depends(get_node_store)
):
    """Execute precise query with multiple filters.

    Supports combined conditions (AND logic) for exact matching.
    """
    try:
        results = node_store.precise_search(
            proposition_query=request.proposition_query,
            raw_content_query=request.raw_content_query,
            tags=request.tags if request.tags else None,
            start_date=request.start_date,
            end_date=request.end_date,
            sort_by=request.sort_by,
            limit=request.limit
        )

        result_items = []
        for node in results:
            # Prioritize refined_content over raw_input
            refined = node.refined_content or node.processed.refined_content or None
            has_refined = bool(refined)

            # For display, use refined_content if available, otherwise truncate raw_input
            if refined:
                display_content = refined[:200] + "..." if len(refined) > 200 else refined
            else:
                display_content = node.raw_input[:200] + "..." if len(node.raw_input) > 200 else node.raw_input

            result_items.append(
                PreciseQueryResultItem(
                    id=node.id,
                    proposition=node.processed.proposition,
                    raw_input=display_content,
                    refined_content=refined,
                    has_refined_content=has_refined,
                    tags=node.tags,
                    timestamp=node.timestamp.isoformat(),
                    source_title=node.source.title,
                    source_location=node.source.location
                )
            )

        return PreciseQueryResponse(
            results=result_items,
            total=len(result_items),
            query={
                "proposition_query": request.proposition_query,
                "raw_content_query": request.raw_content_query,
                "tags": request.tags,
                "start_date": request.start_date.isoformat() if request.start_date else None,
                "end_date": request.end_date.isoformat() if request.end_date else None,
                "sort_by": request.sort_by
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"精准查询失败: {str(e)}")


@router.get("/search")
async def keyword_search(
    q: str,
    limit: int = 10,
    node_store: NodeStore = Depends(get_node_store),
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Simple keyword search in propositions."""
    results = node_store.search_by_proposition(q, limit=limit)

    result_items = []
    for node, score in results:
        # Prioritize refined_content
        refined = node.refined_content or node.processed.refined_content or None

        result_items.append({
            "id": node.id,
            "proposition": node.processed.proposition,
            "refined_content": refined,
            "has_refined_content": bool(refined),
            "tags": node.tags,
            "timestamp": node.timestamp.isoformat(),
            "score": score
        })

    return {
        "results": result_items,
        "query": q,
        "total": len(results)
    }


@router.get("/nodes/{node_id}/related")
async def get_related_nodes(
    node_id: str,
    limit: int = 10,
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Find nodes related to a specific node."""
    try:
        results = await query_engine.get_related_nodes(node_id, limit=limit)
        
        return {
            "results": [_convert_result_to_item(r) for r in results],
            "node_id": node_id,
            "total": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取相关节点失败: {str(e)}")
