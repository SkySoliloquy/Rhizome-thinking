"""Epistemic map API routes - Visualize knowledge distribution."""

import random
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from rhizome.core.node_store import NodeStore
from rhizome.core.theme_store import ThemeStore
from rhizome.api.dependencies import get_node_store

router = APIRouter()


class EpistemicNode(BaseModel):
    """Node in epistemic map."""
    id: str
    proposition: str
    tags: list[str]
    x: float  # 0-1 range, theme distribution
    y: float  # 0-1 range, certainty (definitive=1.0, needs_thinking=0.0)
    cluster_id: int
    cluster_name: str
    timestamp: str
    link_count: int


class EpistemicCluster(BaseModel):
    """Cluster in epistemic map."""
    id: int
    name: str
    node_count: int
    avg_certainty: float
    center_x: float
    center_y: float


class EpistemicMapResponse(BaseModel):
    """Epistemic map response."""
    nodes: list[EpistemicNode]
    clusters: list[EpistemicCluster]
    total_nodes: int
    certainty_distribution: dict[str, int]  # tag -> count


# Certainty mapping for Y axis
def get_certainty_value(tags: list[str]) -> float:
    """Map tags to certainty value (0.0 - 1.0) for Y axis."""
    if "definitive" in tags:
        return 0.8 + random.uniform(0, 0.2)  # 0.8-1.0
    elif "inferred" in tags:
        return 0.6 + random.uniform(0, 0.2)  # 0.6-0.8
    elif "cross-domain" in tags:
        return 0.5 + random.uniform(-0.1, 0.1)  # 0.4-0.6
    elif "vague" in tags:
        return 0.2 + random.uniform(0, 0.3)  # 0.2-0.5
    elif "needs_thinking" in tags:
        return random.uniform(0, 0.2)  # 0.0-0.2
    else:
        return 0.4 + random.uniform(-0.1, 0.1)  # Default


def get_cluster_name(tag: str) -> str:
    """Get display name for cluster based on tag."""
    cluster_names = {
        "definitive": "明确结论",
        "inferred": "推断结论",
        "vague": "模糊感知",
        "needs_thinking": "待思考问题",
        "cross-domain": "跨域连接"
    }
    return cluster_names.get(tag, "其他")


@router.get("/epistemic-map", response_model=EpistemicMapResponse)
async def get_epistemic_map(
    use_themes: bool = Query(default=True, description="使用主题聚类作为X轴"),
    node_store: NodeStore = Depends(get_node_store)
):
    """Get epistemic map - 2D visualization of knowledge distribution.
    
    **Y轴（确定性）**：固定映射
    - definitive: 0.8-1.0
    - inferred: 0.6-0.8  
    - cross-domain: 0.4-0.6
    - vague: 0.2-0.5
    - needs_thinking: 0.0-0.2
    
    **X轴（主题分布）**：动态聚类
    - 按标签或主题分组
    - 同一组内节点在X轴上靠近
    
    适合场景：
    - 全局观察思维分布
    - 发现哪些主题有明确积累
    - 识别停留在模糊阶段的想法
    """
    try:
        all_nodes = node_store.list_all()
        
        if not all_nodes:
            return {
                "nodes": [],
                "clusters": [],
                "total_nodes": 0,
                "certainty_distribution": {}
            }
        
        # Group nodes by primary tag for clustering
        tag_order = ["definitive", "inferred", "cross-domain", "vague", "needs_thinking"]
        tag_clusters = {tag: [] for tag in tag_order}
        
        for node in all_nodes:
            # Find primary tag
            primary_tag = "vague"  # Default
            for tag in tag_order:
                if tag in node.tags:
                    primary_tag = tag
                    break
            tag_clusters[primary_tag].append(node)
        
        # Build clusters
        clusters = []
        nodes_data = []
        certainty_dist = {}
        
        cluster_id = 0
        for tag in tag_order:
            tag_nodes = tag_clusters[tag]
            if not tag_nodes:
                continue
            
            cluster_name = get_cluster_name(tag)
            cluster_node_count = len(tag_nodes)
            
            # Calculate cluster center
            base_x = cluster_id / max(len(tag_order) - 1, 1) if len(tag_order) > 1 else 0.5
            
            # Process nodes in this cluster
            cluster_certainty_sum = 0
            for i, node in enumerate(tag_nodes):
                # Y axis: certainty based on tags
                y = get_certainty_value(node.tags)
                cluster_certainty_sum += y
                
                # X axis: distribute within cluster area
                # Add some randomness for visual separation
                cluster_width = 0.8 / len(tag_order) if len(tag_order) > 1 else 0.8
                x = base_x + (i % 5) * (cluster_width / 5) + random.uniform(-0.05, 0.05)
                x = max(0.05, min(0.95, x))  # Keep within bounds
                
                confirmed_links = len([l for l in node.links if l.confirmed])
                
                nodes_data.append({
                    "id": node.id,
                    "proposition": node.processed.proposition,
                    "tags": node.tags,
                    "x": round(x, 3),
                    "y": round(y, 3),
                    "cluster_id": cluster_id,
                    "cluster_name": cluster_name,
                    "timestamp": node.timestamp.isoformat(),
                    "link_count": confirmed_links
                })
                
                # Update certainty distribution
                for t in node.tags:
                    certainty_dist[t] = certainty_dist.get(t, 0) + 1
            
            # Calculate cluster stats
            avg_certainty = cluster_certainty_sum / cluster_node_count if cluster_node_count > 0 else 0.5
            
            clusters.append({
                "id": cluster_id,
                "name": cluster_name,
                "node_count": cluster_node_count,
                "avg_certainty": round(avg_certainty, 2),
                "center_x": round(base_x + 0.4 / len(tag_order) if len(tag_order) > 1 else 0.5, 2),
                "center_y": round(avg_certainty, 2)
            })
            
            cluster_id += 1
        
        return {
            "nodes": nodes_data,
            "clusters": clusters,
            "total_nodes": len(all_nodes),
            "certainty_distribution": certainty_dist
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取认知地图失败: {str(e)}")


@router.get("/epistemic-map/stats")
async def get_epistemic_stats(
    node_store: NodeStore = Depends(get_node_store)
):
    """Get statistics for epistemic map analysis."""
    try:
        all_nodes = node_store.list_all()
        
        # Calculate distributions
        tag_counts = {}
        certainty_levels = {"high": 0, "medium": 0, "low": 0}
        
        for node in all_nodes:
            for tag in node.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            certainty = get_certainty_value(node.tags)
            if certainty >= 0.6:
                certainty_levels["high"] += 1
            elif certainty >= 0.3:
                certainty_levels["medium"] += 1
            else:
                certainty_levels["low"] += 1
        
        # Find growth over time
        monthly_counts = {}
        for node in all_nodes:
            ym = node.timestamp.strftime("%Y-%m")
            monthly_counts[ym] = monthly_counts.get(ym, 0) + 1
        
        return {
            "total_nodes": len(all_nodes),
            "tag_distribution": tag_counts,
            "certainty_distribution": certainty_levels,
            "monthly_growth": monthly_counts,
            "insights": {
                "dominant_tag": max(tag_counts, key=tag_counts.get) if tag_counts else None,
                "certainty_ratio": {
                    "clear": certainty_levels["high"],
                    "developing": certainty_levels["medium"],
                    "fuzzy": certainty_levels["low"]
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")
