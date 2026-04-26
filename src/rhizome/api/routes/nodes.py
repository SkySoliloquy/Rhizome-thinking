"""Node management API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from rhizome.core.models import Node, Source, TagType
from rhizome.core.node_store import NodeStore
from rhizome.core.llm_processor import LLMProcessor, MockLLMProcessor
from rhizome.core.theme_extractor import ThemeExtractor, MockThemeExtractor
from rhizome.core.theme_store import ThemeStore
from rhizome.core.theme_models import Theme, NodeTheme
from rhizome.retrieval.vector_store import VectorStore, get_vector_store
from rhizome.api.dependencies import get_node_store
from rhizome.retrieval.search_optimizer import invalidate_theme_cache

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateNodeRequest(BaseModel):
    """Request to create a new node."""
    raw_input: str = Field(..., min_length=1, description="原始输入内容")
    source_type: str = Field(default="original", description="来源类型")
    source_title: Optional[str] = Field(default=None, description="来源标题")
    source_location: Optional[str] = Field(default=None, description="来源位置")


class UpdateNodeRequest(BaseModel):
    """Request to update an existing node."""
    proposition: Optional[str] = Field(default=None, description="核心命题")
    raw_input: Optional[str] = Field(default=None, description="原始输入内容")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    open_questions: Optional[list[str]] = Field(default=None, description="开放问题列表")
    source_title: Optional[str] = Field(default=None, description="来源标题")
    source_location: Optional[str] = Field(default=None, description="来源位置")


class CreateNodeResponse(BaseModel):
    """Response after creating a node."""
    node: Node
    potential_links: list[dict]
    message: str = "节点创建成功"


class NodeListResponse(BaseModel):
    """Response for listing nodes."""
    nodes: list[Node]
    total: int
    limit: int
    offset: int


class NodeDetailResponse(BaseModel):
    """Detailed node response."""
    node: Node
    related_nodes: list[dict]


@router.post("/nodes", response_model=CreateNodeResponse)
async def create_node(
    request: CreateNodeRequest,
    node_store: NodeStore = Depends(get_node_store),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Create a new knowledge node.

    1. Process raw input with LLM
    2. Generate embeddings
    3. Store in both file system and vector database
    """
    try:
        # Create source
        source = Source(
            type=request.source_type,  # type: ignore
            title=request.source_title,
            location=request.source_location
        )

        # Get existing nodes for link suggestions
        existing_nodes = node_store.list_all(limit=50)

        # Try to use real LLM processor, fallback to mock if it fails
        processor = LLMProcessor()
        try:
            processed, tags, potential_links = await processor.process(
                raw_input=request.raw_input,
                source=source,
                existing_nodes=existing_nodes
            )
            logger.info("Using real LLM processor")
        except Exception as llm_error:
            logger.warning(f"LLM processor failed, using mock: {llm_error}")
            # Fallback to mock processor
            mock_processor = MockLLMProcessor()
            processed, tags, potential_links = await mock_processor.process(
                raw_input=request.raw_input,
                source=source,
                existing_nodes=existing_nodes
            )

        # Create node first (without links)
        node = Node(
            source=source,
            raw_input=request.raw_input,
            processed=processed,
            tags=tags  # type: ignore
        )

        # Match potential_links to existing nodes and create Link objects
        from rhizome.core.models import Link as LinkModel

        for link_suggestion in potential_links:
            # Find matching existing node by comparing summaries with propositions
            target_summary = link_suggestion.get("target_node_summary", "")
            relation_type = link_suggestion.get("relation_type", "analogy")
            reasoning = link_suggestion.get("reasoning", "")
            strength = 0.5  # Default strength

            # Use character 2-gram overlap for Chinese text
            def get_ngrams(text, n=2):
                return set(text[i:i+n] for i in range(len(text) - n + 1))

            target_ngrams = get_ngrams(target_summary.lower())

            # Find best matching existing node using character-level similarity
            best_match = None
            best_jaccard = 0.0
            for existing_node in existing_nodes:
                existing_proposition = existing_node.processed.proposition
                existing_ngrams = get_ngrams(existing_proposition.lower())

                if not target_ngrams or not existing_ngrams:
                    continue

                overlap = len(target_ngrams & existing_ngrams)
                union = len(target_ngrams | existing_ngrams)
                jaccard = overlap / union if union > 0 else 0

                if jaccard > best_jaccard and jaccard >= 0.05:  # At least 5% character overlap
                    best_jaccard = jaccard
                    best_match = existing_node

            if best_match:
                # Check if this link already exists to avoid duplicates
                existing_link_ids = [link.target_id for link in node.links]
                if best_match.id not in existing_link_ids:
                    link = LinkModel(
                        target_id=best_match.id,
                        relation_type=relation_type,  # type: ignore
                        strength=strength,
                        confirmed=False,
                        auto_confirmed=False,
                        reason=reasoning if reasoning else None
                    )
                    node.links.append(link)
                    logger.info(f"Created link: {node.id[:8]} -> {best_match.id[:8]} ({relation_type})")

        # Save to file system
        node_store.save(node)

        # Add to vector store
        await vector_store.add_node(node)

        # Extract themes from the new node (async, non-blocking)
        try:
            await extract_themes_for_node(node)
            invalidate_theme_cache()
            logger.info(f"Themes extracted for node {node.id[:8]}")
        except Exception as theme_error:
            logger.warning(f"Theme extraction failed for node {node.id[:8]}: {theme_error}")
            # Don't fail the node creation if theme extraction fails

        return CreateNodeResponse(
            node=node,
            potential_links=potential_links
        )
        
    except Exception as e:
        logger.exception("Failed to create node")
        raise HTTPException(status_code=500, detail=f"创建节点失败: {str(e)}")


@router.get("/nodes", response_model=NodeListResponse)
async def list_nodes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tag: Optional[str] = Query(default=None, description="按标签过滤"),
    node_store: NodeStore = Depends(get_node_store)
):
    """List all nodes with optional filtering."""
    if tag:
        nodes = node_store.list_by_tag(tag, limit=limit)
    else:
        nodes = node_store.list_all(limit=limit, offset=offset)
    
    # Get total count
    stats = node_store.get_stats()
    total = stats.get("total_nodes", 0)
    
    return NodeListResponse(
        nodes=nodes,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/nodes/{node_id}", response_model=NodeDetailResponse)
async def get_node(
    node_id: str,
    node_store: NodeStore = Depends(get_node_store)
):
    """Get a single node by ID."""
    node = node_store.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点未找到")
    
    # Get related nodes (connected nodes)
    related = []
    for link in node.links:
        target = node_store.get(link.target_id)
        if target:
            related.append({
                "node": target,
                "relation_type": link.relation_type,
                "strength": link.strength,
                "confirmed": link.confirmed,
                "reason": link.reason
            })
    
    return NodeDetailResponse(
        node=node,
        related_nodes=related
    )


@router.put("/nodes/{node_id}")
async def update_node(
    node_id: str,
    request: UpdateNodeRequest,
    node_store: NodeStore = Depends(get_node_store)
):
    """Update a node."""
    if not node_store.exists(node_id):
        raise HTTPException(status_code=404, detail="节点未找到")

    updated_node = node_store.update_node(
        node_id=node_id,
        proposition=request.proposition,
        raw_input=request.raw_input,
        tags=request.tags,
        open_questions=request.open_questions,
        source_title=request.source_title,
        source_location=request.source_location
    )

    if not updated_node:
        raise HTTPException(status_code=500, detail="更新节点失败")

    invalidate_theme_cache()

    return {
        "message": "节点已更新",
        "node_id": node_id,
        "node": updated_node
    }


@router.delete("/nodes/{node_id}")
async def delete_node(
    node_id: str,
    node_store: NodeStore = Depends(get_node_store),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Delete a node."""
    if not node_store.exists(node_id):
        raise HTTPException(status_code=404, detail="节点未找到")

    # Delete from file system
    node_store.delete(node_id)

    # Delete from vector store
    vector_store.delete_node(node_id)

    invalidate_theme_cache()

    return {"message": "节点已删除", "node_id": node_id}


async def extract_themes_for_node(node: Node) -> list[Theme]:
    """Extract themes from a node and manage theme merging.
    
    This implements:
    - One-to-many: One node can have multiple themes
    - Many-to-one: Multiple nodes can share the same theme (if similar)
    """
    # Initialize extractor and store
    try:
        extractor = ThemeExtractor()
    except ValueError:
        extractor = MockThemeExtractor()
    
    theme_store = ThemeStore()
    
    # Extract themes from node
    extracted_themes = await extractor.extract_themes_from_node(node)
    
    created_themes = []
    node_themes = NodeTheme(node_id=node.id)
    
    for theme_data in extracted_themes:
        summary = theme_data["summary"]
        tag = theme_data["tag"]
        keywords = theme_data.get("keywords", [])
        
        # Check for similar existing themes (many-to-one)
        existing_themes = theme_store.list_themes_by_tag(tag)
        matched_theme = None
        
        for existing in existing_themes:
            # Use similarity check to find matching themes
            similarity = extractor._calculate_similarity(existing.summary, summary)
            if similarity >= 0.6:  # Threshold for theme merging
                matched_theme = existing
                break
        
        if matched_theme:
            # Add node to existing theme (many-to-one)
            matched_theme.add_node(node.id)
            # Merge keywords
            for kw in keywords:
                if kw not in matched_theme.keywords:
                    matched_theme.keywords.append(kw)
            theme_store.save_theme(matched_theme)
            created_themes.append(matched_theme)
            if matched_theme.id not in node_themes.theme_ids:
                node_themes.theme_ids.append(matched_theme.id)
        else:
            # Create new theme (one-to-many)
            new_theme = Theme(
                summary=summary,
                tag=tag,
                keywords=keywords,
                node_ids=[node.id]
            )
            theme_store.save_theme(new_theme)
            created_themes.append(new_theme)
            node_themes.theme_ids.append(new_theme.id)
    
    # Save node-theme association
    if node_themes.theme_ids:
        theme_store.save_node_themes(node_themes)
    
    return created_themes


@router.get("/tags")
async def get_tags(
    node_store: NodeStore = Depends(get_node_store)
):
    """Get all tags with counts."""
    stats = node_store.get_stats()
    tag_counts = stats.get("tag_counts", {})
    
    tag_display_names = {
        "definitive": "明确结论",
        "inferred": "推断结论",
        "vague": "模糊感知",
        "needs_thinking": "待思考问题",
        "cross-domain": "跨域连接"
    }
    
    return {
        "tags": [
            {
                "id": tag,
                "name": tag_display_names.get(tag, tag),
                "count": count
            }
            for tag, count in sorted(
                tag_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]
    }
