"""Query API routes for semantic search."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rhizome.retrieval.query_engine import QueryEngine, QueryModifiers, QueryResult
from rhizome.api.dependencies import get_query_engine

router = APIRouter()


class QueryRequest(BaseModel):
    """Semantic query request."""
    anchor: str = Field(..., min_length=1, description="语义锚点 - 查询的核心内容")
    modifiers: QueryModifiers = Field(
        default_factory=QueryModifiers,
        description="查询修饰符 - 用于过滤结果"
    )


class QueryResultItem(BaseModel):
    """Single query result item."""
    id: str
    proposition: str
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
    return QueryResultItem(
        id=result.node.id,
        proposition=result.node.processed.proposition,
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


@router.get("/search")
async def keyword_search(
    q: str,
    limit: int = 10,
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Simple keyword search in propositions."""
    # Use node_store for keyword search
    from rhizome.core.node_store import NodeStore
    
    node_store = NodeStore()
    results = node_store.search_by_proposition(q, limit=limit)
    
    return {
        "results": [
            {
                "id": node.id,
                "proposition": node.processed.proposition,
                "tags": node.tags,
                "timestamp": node.timestamp.isoformat(),
                "score": score
            }
            for node, score in results
        ],
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
