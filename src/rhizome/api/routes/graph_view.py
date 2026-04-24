"""Graph view API routes - Network visualization of node relationships."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from rhizome.core.node_store import NodeStore
from rhizome.api.dependencies import get_node_store

router = APIRouter()


class GraphNode(BaseModel):
    """Node in graph visualization."""
    id: str
    label: str  # Shortened proposition
    full_text: str
    tags: list[str]
    tag_color: str  # Color based on primary tag
    link_count: int
    is_isolated: bool


class GraphEdge(BaseModel):
    """Edge/link in graph visualization."""
    source: str
    target: str
    relation_type: str
    relation_name: str
    strength: float
    width: float  # Calculated from strength
    color: str  # Color based on relation type


class GraphStats(BaseModel):
    """Statistics for graph view."""
    total_nodes: int
    total_edges: int
    isolated_nodes: int
    relation_type_counts: dict[str, int]


class GraphViewResponse(BaseModel):
    """Graph view response."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: GraphStats


# Color schemes
TAG_COLORS = {
    "definitive": "#00b894",      # Green
    "inferred": "#a29bfe",        # Purple
    "vague": "#fdcb6e",           # Yellow
    "needs_thinking": "#e74c3c",  # Red
    "cross-domain": "#00cec9"     # Cyan
}

RELATION_COLORS = {
    "support": "#00b894",     # Green
    "contradict": "#e74c3c",  # Red
    "extend": "#6c5ce7",      # Purple
    "source": "#fdcb6e",      # Yellow
    "analogy": "#00cec9"      # Cyan
}

RELATION_NAMES = {
    "support": "支持",
    "contradict": "矛盾",
    "extend": "延伸",
    "source": "来源",
    "analogy": "类比"
}


def shorten_text(text: str, max_len: int = 100) -> str:
    """Shorten text for node label."""
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


@router.get("/graph", response_model=GraphViewResponse)
async def get_graph_view(
    include_unconfirmed: bool = Query(default=False, description="包含未确认的连接"),
    min_strength: float = Query(default=0.0, ge=0.0, le=1.0, description="最小连接强度"),
    relation_filter: Optional[str] = Query(default=None, description="筛选特定关系类型"),
    node_store: NodeStore = Depends(get_node_store)
):
    """Get graph view - network visualization of node relationships.
    
    可视化元素：
    - **节点圆点**: 代表知识节点，颜色按标签区分
    - **连线**: 代表节点间的连接关系，粗细表示连接强度
    - **关系标签**: 连线上的文字说明
    - **孤立节点**: 无连线的节点以灰色显示
    
    交互功能（前端实现）：
    - 拖拽移动节点
    - 滚轮缩放画布
    - 点击节点查看详情
    - 双击节点聚焦其直接连接
    - 筛选特定关系类型
    """
    try:
        all_nodes = node_store.list_all()
        
        if not all_nodes:
            return {
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "isolated_nodes": 0,
                    "relation_type_counts": {}
                }
            }
        
        # Build node map
        node_map = {node.id: node for node in all_nodes}
        
        # Build nodes
        graph_nodes = []
        node_ids_with_edges = set()
        
        for node in all_nodes:
            # Determine primary tag and color
            primary_tag = "vague"
            for tag in ["definitive", "inferred", "cross-domain", "vague", "needs_thinking"]:
                if tag in node.tags:
                    primary_tag = tag
                    break
            
            # Count confirmed links
            confirmed_links = [l for l in node.links if l.confirmed or include_unconfirmed]
            if include_unconfirmed:
                confirmed_links = node.links
            
            link_count = len(confirmed_links)
            
            graph_nodes.append({
                "id": node.id,
                "label": shorten_text(node.processed.proposition),
                "full_text": node.processed.proposition,
                "tags": node.tags,
                "tag_color": TAG_COLORS.get(primary_tag, "#95a5a6"),
                "link_count": link_count,
                "is_isolated": link_count == 0
            })
        
        # Build edges
        graph_edges = []
        relation_counts = {}
        
        for node in all_nodes:
            for link in node.links:
                # Skip unconfirmed unless requested
                if not link.confirmed and not include_unconfirmed:
                    continue
                
                # Skip if target doesn't exist
                if link.target_id not in node_map:
                    continue
                
                # Skip if strength is below threshold
                if link.strength < min_strength:
                    continue
                
                # Skip if relation type doesn't match filter
                if relation_filter and link.relation_type != relation_filter:
                    continue
                
                # Track nodes with edges
                node_ids_with_edges.add(node.id)
                node_ids_with_edges.add(link.target_id)
                
                # Count relation types
                relation_counts[link.relation_type] = relation_counts.get(link.relation_type, 0) + 1
                
                # Calculate edge width (1-8 pixels based on strength)
                width = 1 + link.strength * 7
                
                graph_edges.append({
                    "source": node.id,
                    "target": link.target_id,
                    "relation_type": link.relation_type,
                    "relation_name": RELATION_NAMES.get(link.relation_type, link.relation_type),
                    "strength": round(link.strength, 2),
                    "width": round(width, 1),
                    "color": RELATION_COLORS.get(link.relation_type, "#95a5a6")
                })
        
        # Mark isolated nodes
        for node in graph_nodes:
            node["is_isolated"] = node["id"] not in node_ids_with_edges
            if node["is_isolated"]:
                node["tag_color"] = "#bdc3c7"  # Gray for isolated
        
        isolated_count = sum(1 for n in graph_nodes if n["is_isolated"])
        
        return {
            "nodes": graph_nodes,
            "edges": graph_edges,
            "stats": {
                "total_nodes": len(graph_nodes),
                "total_edges": len(graph_edges),
                "isolated_nodes": isolated_count,
                "relation_type_counts": relation_counts
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取关系图失败: {str(e)}")


@router.get("/graph/node/{node_id}/neighbors")
async def get_node_neighbors(
    node_id: str,
    depth: int = Query(default=1, ge=1, le=3, description="邻居深度（1-3层）"),
    node_store: NodeStore = Depends(get_node_store)
):
    """Get neighborhood graph for a specific node.
    
    用于：
    - 双击节点时聚焦显示
    - 查看节点的局部关系网络
    """
    try:
        center_node = node_store.get(node_id)
        if not center_node:
            raise HTTPException(status_code=404, detail="节点未找到")
        
        all_nodes = node_store.list_all()
        node_map = {n.id: n for n in all_nodes}
        
        # BFS to find neighbors
        visited = {node_id}
        current_level = {node_id}
        nodes_to_include = {node_id}
        edges_to_include = []
        
        for _ in range(depth):
            next_level = set()
            for nid in current_level:
                node = node_map.get(nid)
                if not node:
                    continue
                
                for link in node.links:
                    if not link.confirmed:
                        continue
                    
                    edges_to_include.append({
                        "source": nid,
                        "target": link.target_id,
                        "relation_type": link.relation_type,
                        "relation_name": RELATION_NAMES.get(link.relation_type, link.relation_type),
                        "strength": round(link.strength, 2),
                        "width": round(1 + link.strength * 7, 1),
                        "color": RELATION_COLORS.get(link.relation_type, "#95a5a6")
                    })
                    
                    if link.target_id not in visited and link.target_id in node_map:
                        visited.add(link.target_id)
                        next_level.add(link.target_id)
                        nodes_to_include.add(link.target_id)
            
            current_level = next_level
        
        # Build nodes
        graph_nodes = []
        for nid in nodes_to_include:
            node = node_map.get(nid)
            if not node:
                continue
            
            primary_tag = "vague"
            for tag in ["definitive", "inferred", "cross-domain", "vague", "needs_thinking"]:
                if tag in node.tags:
                    primary_tag = tag
                    break
            
            confirmed_links = [l for l in node.links if l.confirmed]
            
            graph_nodes.append({
                "id": node.id,
                "label": shorten_text(node.processed.proposition),
                "full_text": node.processed.proposition,
                "tags": node.tags,
                "tag_color": TAG_COLORS.get(primary_tag, "#95a5a6"),
                "link_count": len(confirmed_links),
                "is_isolated": False,
                "is_center": nid == node_id
            })
        
        return {
            "center_node_id": node_id,
            "nodes": graph_nodes,
            "edges": edges_to_include,
            "depth": depth
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取节点邻居失败: {str(e)}")


@router.get("/graph/stats")
async def get_graph_statistics(
    node_store: NodeStore = Depends(get_node_store)
):
    """Get detailed statistics for graph analysis."""
    try:
        all_nodes = node_store.list_all()
        
        # Calculate metrics
        total_links = 0
        confirmed_links = 0
        relation_counts = {}
        
        for node in all_nodes:
            for link in node.links:
                total_links += 1
                if link.confirmed:
                    confirmed_links += 1
                    relation_counts[link.relation_type] = relation_counts.get(link.relation_type, 0) + 1
        
        # Find most connected nodes
        node_link_counts = []
        for node in all_nodes:
            count = len([l for l in node.links if l.confirmed])
            node_link_counts.append((node.id, node.processed.proposition[:200], count))
        
        node_link_counts.sort(key=lambda x: x[2], reverse=True)
        
        return {
            "total_nodes": len(all_nodes),
            "total_links": total_links,
            "confirmed_links": confirmed_links,
            "pending_links": total_links - confirmed_links,
            "relation_distribution": relation_counts,
            "most_connected_nodes": [
                {"id": nid, "proposition": prop, "link_count": count}
                for nid, prop, count in node_link_counts[:5]
            ],
            "average_links_per_node": round(confirmed_links / len(all_nodes), 2) if all_nodes else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")
