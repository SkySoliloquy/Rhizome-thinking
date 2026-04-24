"""Statistics API routes."""

from fastapi import APIRouter, Depends

from rhizome.core.node_store import NodeStore
from rhizome.retrieval.vector_store import VectorStore, get_vector_store
from rhizome.api.dependencies import get_node_store

router = APIRouter()


@router.get("/stats")
async def get_stats(
    node_store: NodeStore = Depends(get_node_store),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Get overall system statistics."""
    node_stats = node_store.get_stats()
    vector_stats = vector_store.get_stats()
    
    tag_display_names = {
        "definitive": "明确结论",
        "inferred": "推断结论",
        "vague": "模糊感知",
        "needs_thinking": "待思考问题",
        "cross-domain": "跨域连接"
    }
    
    # Format tag counts with display names
    tag_counts = {
        tag_display_names.get(tag, tag): count
        for tag, count in node_stats.get("tag_counts", {}).items()
    }
    
    return {
        "nodes": {
            "total": node_stats.get("total_nodes", 0),
            "tag_distribution": tag_counts
        },
        "links": {
            "total": node_stats.get("total_links", 0),
            "confirmed": node_stats.get("confirmed_links", 0),
            "pending": node_stats.get("pending_links", 0)
        },
        "vector_store": {
            "total_vectors": vector_stats.get("total_vectors", 0)
        },
        "last_updated": node_stats.get("last_updated")
    }


@router.get("/stats/recent")
async def get_recent_activity(
    days: int = 7,
    node_store: NodeStore = Depends(get_node_store)
):
    """Get recent activity statistics."""
    from datetime import datetime, timedelta
    
    cutoff = datetime.now() - timedelta(days=days)
    
    # Get all nodes
    all_nodes = node_store.list_all()
    
    # Filter recent nodes
    recent_nodes = [
        node for node in all_nodes
        if node.timestamp >= cutoff
    ]
    
    # Count by day
    daily_counts = {}
    for node in recent_nodes:
        day_key = node.timestamp.strftime("%Y-%m-%d")
        daily_counts[day_key] = daily_counts.get(day_key, 0) + 1
    
    # Fill in missing days
    current = cutoff.date()
    end = datetime.now().date()
    while current <= end:
        day_str = current.strftime("%Y-%m-%d")
        if day_str not in daily_counts:
            daily_counts[day_str] = 0
        current += timedelta(days=1)
    
    return {
        "period_days": days,
        "total_new_nodes": len(recent_nodes),
        "daily_activity": dict(sorted(daily_counts.items())),
        "recent_nodes": [
            {
                "id": node.id,
                "proposition": node.processed.proposition[:500],
                "timestamp": node.timestamp.isoformat()
            }
            for node in sorted(recent_nodes, key=lambda n: n.timestamp, reverse=True)[:10]
        ]
    }
