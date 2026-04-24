"""Outline view API routes - Timeline overview of knowledge base."""

from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from rhizome.core.node_store import NodeStore
from rhizome.api.dependencies import get_node_store

router = APIRouter()


class NodeOutlineItem(BaseModel):
    """Node item in outline view."""
    id: str
    proposition: str
    tags: list[str]
    timestamp: str
    link_count: int
    is_isolated: bool


class MonthGroup(BaseModel):
    """Nodes grouped by month."""
    year_month: str
    display_name: str
    nodes: list[NodeOutlineItem]
    node_count: int


class OutlineStats(BaseModel):
    """Statistics for outline view."""
    total_nodes: int
    isolated_nodes: int
    high_connection_nodes: int  # Nodes with 3+ links
    monthly_counts: dict[str, int]


class OutlineResponse(BaseModel):
    """Outline view response."""
    months: list[MonthGroup]
    stats: OutlineStats


@router.get("/outline", response_model=OutlineResponse)
async def get_outline_view(
    sort_by: Literal["time", "links", "tag"] = Query(default="time", description="排序方式"),
    tag_filter: Optional[str] = Query(default=None, description="按标签筛选"),
    node_store: NodeStore = Depends(get_node_store)
):
    """Get outline view - timeline overview of all nodes.
    
    用途：
    - 发现孤立节点（没有任何连接）
    - 发现高连接节点（核心概念）
    - 回顾某段时间内的思考轨迹
    
    Args:
        sort_by: 排序方式 (time=时间, links=连接数, tag=标签)
        tag_filter: 筛选特定标签的节点
    
    Returns:
        按月份分组的节点列表和统计信息
    """
    try:
        # Get all nodes
        all_nodes = node_store.list_all()
        
        # Filter by tag if specified
        if tag_filter and tag_filter != "all":
            all_nodes = [n for n in all_nodes if tag_filter in n.tags]
        
        # Calculate link counts and isolation status
        node_info = []
        for node in all_nodes:
            link_count = len(node.links)
            confirmed_links = len([l for l in node.links if l.confirmed])
            is_isolated = confirmed_links == 0
            
            node_info.append({
                "node": node,
                "link_count": confirmed_links,
                "is_isolated": is_isolated
            })
        
        # Sort based on sort_by parameter
        if sort_by == "time":
            node_info.sort(key=lambda x: x["node"].timestamp, reverse=True)
        elif sort_by == "links":
            node_info.sort(key=lambda x: x["link_count"], reverse=True)
        elif sort_by == "tag":
            # Sort by first tag, then by time
            node_info.sort(key=lambda x: (x["node"].tags[0] if x["node"].tags else "", x["node"].timestamp), reverse=True)
        
        # Group by month
        month_groups: dict[str, list] = {}
        for info in node_info:
            node = info["node"]
            year_month = node.timestamp.strftime("%Y-%m")
            
            if year_month not in month_groups:
                month_groups[year_month] = []
            
            month_groups[year_month].append({
                "id": node.id,
                "proposition": node.processed.proposition,
                "tags": node.tags,
                "timestamp": node.timestamp.isoformat(),
                "link_count": info["link_count"],
                "is_isolated": info["is_isolated"]
            })
        
        # Build month groups
        months = []
        for year_month in sorted(month_groups.keys(), reverse=True):
            nodes = month_groups[year_month]
            year, month = year_month.split("-")
            
            months.append({
                "year_month": year_month,
                "display_name": f"{year}年{int(month)}月",
                "nodes": nodes,
                "node_count": len(nodes)
            })
        
        # Calculate stats
        isolated_count = sum(1 for info in node_info if info["is_isolated"])
        high_conn_count = sum(1 for info in node_info if info["link_count"] >= 3)
        monthly_counts = {m["year_month"]: m["node_count"] for m in months}
        
        return {
            "months": months,
            "stats": {
                "total_nodes": len(all_nodes),
                "isolated_nodes": isolated_count,
                "high_connection_nodes": high_conn_count,
                "monthly_counts": monthly_counts
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取大纲视图失败: {str(e)}")


@router.get("/outline/isolated")
async def get_isolated_nodes(
    limit: int = Query(default=50, ge=1, le=200),
    node_store: NodeStore = Depends(get_node_store)
):
    """Get isolated nodes (nodes with no confirmed links).
    
    孤立节点可能是被遗忘的想法，值得重新审视。
    """
    try:
        all_nodes = node_store.list_all()
        isolated = []
        
        for node in all_nodes:
            confirmed_links = [l for l in node.links if l.confirmed]
            if len(confirmed_links) == 0:
                isolated.append({
                    "id": node.id,
                    "proposition": node.processed.proposition,
                    "tags": node.tags,
                    "timestamp": node.timestamp.isoformat(),
                    "age_days": (datetime.now() - node.timestamp).days
                })
        
        # Sort by age (oldest first - they've been isolated longer)
        isolated.sort(key=lambda x: x["timestamp"])
        
        return {
            "isolated_nodes": isolated[:limit],
            "total_isolated": len(isolated),
            "total_nodes": len(all_nodes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取孤立节点失败: {str(e)}")


@router.get("/outline/high-connections")
async def get_high_connection_nodes(
    min_links: int = Query(default=3, ge=1, description="最小连接数"),
    limit: int = Query(default=20, ge=1, le=100),
    node_store: NodeStore = Depends(get_node_store)
):
    """Get nodes with many connections (core concepts in thinking).
    
    高连接节点是思维中的核心概念，值得重点关注。
    """
    try:
        all_nodes = node_store.list_all()
        high_conn_nodes = []
        
        for node in all_nodes:
            confirmed_links = [l for l in node.links if l.confirmed]
            if len(confirmed_links) >= min_links:
                high_conn_nodes.append({
                    "id": node.id,
                    "proposition": node.processed.proposition,
                    "tags": node.tags,
                    "timestamp": node.timestamp.isoformat(),
                    "link_count": len(confirmed_links),
                    "links": [
                        {
                            "target_id": l.target_id,
                            "relation_type": l.relation_type,
                            "strength": l.strength
                        }
                        for l in confirmed_links[:5]  # Include first 5 links
                    ]
                })
        
        # Sort by link count
        high_conn_nodes.sort(key=lambda x: x["link_count"], reverse=True)
        
        return {
            "high_connection_nodes": high_conn_nodes[:limit],
            "min_links_threshold": min_links,
            "total_matching": len(high_conn_nodes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取高连接节点失败: {str(e)}")
