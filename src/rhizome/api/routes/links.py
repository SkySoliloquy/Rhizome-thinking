"""Link management API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rhizome.core.node_store import NodeStore
from rhizome.core.models import Link, RelationType
from rhizome.api.dependencies import get_node_store

router = APIRouter()


class CreateLinkRequest(BaseModel):
    """Request to create a link."""
    source_id: str = Field(..., description="源节点ID")
    target_id: str = Field(..., description="目标节点ID")
    relation_type: str = Field(..., description="关系类型")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="连接强度")
    confirmed: bool = Field(default=True, description="是否已确认")


class UpdateLinkRequest(BaseModel):
    """Request to update a link."""
    confirmed: Optional[bool] = None
    strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class LinkResponse(BaseModel):
    """Link response."""
    source_id: str
    target_id: str
    relation_type: str
    strength: float
    confirmed: bool
    relation_name: str


@router.post("/links")
async def create_link(
    request: CreateLinkRequest,
    node_store: NodeStore = Depends(get_node_store)
):
    """Create a new link between nodes."""
    # Validate relation type
    valid_types = ["support", "contradict", "extend", "source", "analogy"]
    if request.relation_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的关系类型。有效类型: {', '.join(valid_types)}"
        )
    
    # Check if source node exists
    if not node_store.exists(request.source_id):
        raise HTTPException(status_code=404, detail="源节点未找到")
    
    # Check if target node exists
    if not node_store.exists(request.target_id):
        raise HTTPException(status_code=404, detail="目标节点未找到")
    
    # Add link
    success = node_store.add_link(
        node_id=request.source_id,
        target_id=request.target_id,
        relation_type=request.relation_type,
        strength=request.strength,
        confirmed=request.confirmed
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="连接已存在或创建失败")
    
    relation_names = {
        "support": "支持",
        "contradict": "矛盾",
        "extend": "延伸",
        "source": "来源",
        "analogy": "类比"
    }
    
    return {
        "message": "连接创建成功",
        "link": {
            "source_id": request.source_id,
            "target_id": request.target_id,
            "relation_type": request.relation_type,
            "strength": request.strength,
            "confirmed": request.confirmed,
            "relation_name": relation_names.get(request.relation_type, request.relation_type)
        }
    }


@router.get("/nodes/{node_id}/links")
async def get_node_links(
    node_id: str,
    include_unconfirmed: bool = True,
    node_store: NodeStore = Depends(get_node_store)
):
    """Get all links for a node."""
    node = node_store.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点未找到")
    
    relation_names = {
        "support": "支持",
        "contradict": "矛盾",
        "extend": "延伸",
        "source": "来源",
        "analogy": "类比"
    }
    
    links = []
    for link in node.links:
        if not include_unconfirmed and not link.confirmed:
            continue
        
        target = node_store.get(link.target_id)
        links.append({
            "target_id": link.target_id,
            "target_proposition": target.processed.proposition if target else "未知节点",
            "relation_type": link.relation_type,
            "relation_name": relation_names.get(link.relation_type, link.relation_type),
            "strength": link.strength,
            "confirmed": link.confirmed
        })
    
    return {
        "node_id": node_id,
        "links": links,
        "total": len(links)
    }


@router.put("/nodes/{node_id}/links/{target_id}")
async def update_link(
    node_id: str,
    target_id: str,
    request: UpdateLinkRequest,
    node_store: NodeStore = Depends(get_node_store)
):
    """Update a link's confirmation status or strength."""
    node = node_store.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点未找到")
    
    # Find and update link
    updated = False
    for link in node.links:
        if link.target_id == target_id:
            if request.confirmed is not None:
                link.confirmed = request.confirmed
            if request.strength is not None:
                link.strength = request.strength
            updated = True
            break
    
    if not updated:
        raise HTTPException(status_code=404, detail="连接未找到")
    
    # Save node
    node_store.save(node)
    
    return {
        "message": "连接已更新",
        "node_id": node_id,
        "target_id": target_id
    }


@router.post("/nodes/{node_id}/links/{target_id}/confirm")
async def confirm_link(
    node_id: str,
    target_id: str,
    node_store: NodeStore = Depends(get_node_store)
):
    """Confirm a link (convenience endpoint)."""
    success = node_store.update_link(node_id, target_id, confirmed=True)
    
    if not success:
        raise HTTPException(status_code=404, detail="连接未找到")
    
    return {
        "message": "连接已确认",
        "node_id": node_id,
        "target_id": target_id
    }


@router.post("/nodes/{node_id}/links/{target_id}/reject")
async def reject_link(
    node_id: str,
    target_id: str,
    node_store: NodeStore = Depends(get_node_store)
):
    """Reject/unconfirm a link (convenience endpoint)."""
    success = node_store.update_link(node_id, target_id, confirmed=False)
    
    if not success:
        raise HTTPException(status_code=404, detail="连接未找到")
    
    return {
        "message": "连接已拒绝",
        "node_id": node_id,
        "target_id": target_id
    }
