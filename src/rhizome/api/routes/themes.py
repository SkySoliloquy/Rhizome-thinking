"""Theme aggregation API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from rhizome.core.theme_models import Theme, AggregatedSearchResult
from rhizome.core.theme_store import ThemeStore
from rhizome.core.node_store import NodeStore
from rhizome.retrieval.query_engine import QueryEngine, QueryModifiers
from rhizome.retrieval.llm_search import LLMSearchReranker, MockLLMSearchReranker
from rhizome.api.dependencies import get_query_engine
from rhizome.config import settings

router = APIRouter()


class ThemeResponse(BaseModel):
    """Theme response model."""
    id: str
    summary: str
    tag: str
    node_count: int
    keywords: list[str]
    node_ids: list[str]
    created_at: str
    updated_at: str


class AggregatedSearchResponse(BaseModel):
    """Aggregated search response."""
    query: str
    total_themes: int
    results: list[dict]  # Tag -> themes mapping


class ThemeDetailResponse(BaseModel):
    """Theme detail with full node information."""
    theme: ThemeResponse
    nodes: list[dict]


def _convert_theme_to_response(theme: Theme) -> ThemeResponse:
    """Convert Theme to response model."""
    return ThemeResponse(
        id=theme.id,
        summary=theme.summary,
        tag=theme.tag,
        node_count=len(theme.node_ids),
        keywords=theme.keywords,
        node_ids=theme.node_ids,
        created_at=theme.created_at.isoformat(),
        updated_at=theme.updated_at.isoformat()
    )


def _traditional_theme_search(anchor: str, themes: list[Theme]) -> list[tuple[Theme, float]]:
    """Traditional keyword-based theme search as fallback.
    
    Args:
        anchor: Search query
        themes: List of themes to search
        
    Returns:
        List of (theme, similarity_score) tuples sorted by relevance
    """
    from rhizome.core.theme_extractor import ThemeExtractor
    extractor = ThemeExtractor()
    
    anchor_lower = anchor.lower()
    theme_scores = []
    
    for theme in themes:
        theme_summary_lower = theme.summary.lower()
        
        # Method 1: Direct substring match (highest priority)
        if anchor_lower in theme_summary_lower or theme_summary_lower in anchor_lower:
            similarity = 0.9
        # Method 2: Word overlap match
        else:
            anchor_words = set(anchor_lower.split())
            theme_words = set(theme_summary_lower.split())
            if anchor_words and theme_words:
                overlap = len(anchor_words & theme_words)
                similarity = overlap / max(len(anchor_words), len(theme_words)) * 0.8
            else:
                similarity = 0.0
        
        # Method 3: Jaccard similarity as fallback
        if similarity < 0.3:
            jaccard_sim = extractor._calculate_similarity(theme.summary, anchor)
            similarity = max(similarity, jaccard_sim * 0.5)
        
        # Boost score if keywords match
        for kw in theme.keywords:
            if kw.lower() in anchor_lower:
                similarity += 0.15
        
        theme_scores.append((theme, min(similarity, 1.0)))
    
    # Sort by similarity
    theme_scores.sort(key=lambda x: x[1], reverse=True)
    return theme_scores


@router.get("/themes", response_model=list[ThemeResponse])
async def list_themes(
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
    limit: int = Query(default=50, ge=1, le=200)
):
    """List all themes with optional filtering."""
    theme_store = ThemeStore()
    
    if tag:
        themes = theme_store.list_themes_by_tag(tag)
    else:
        themes = theme_store.get_all_themes()
    
    # Sort by node count (descending) and limit
    themes.sort(key=lambda t: -t.node_count)
    themes = themes[:limit]
    
    return [_convert_theme_to_response(t) for t in themes]


@router.get("/themes/stats")
async def get_theme_stats():
    """Get theme statistics."""
    theme_store = ThemeStore()
    return theme_store.get_stats()


@router.get("/themes/{theme_id}", response_model=ThemeDetailResponse)
async def get_theme_detail(
    theme_id: str,
    include_nodes: bool = Query(default=True, description="Include full node data")
):
    """Get detailed information about a theme including related nodes."""
    theme_store = ThemeStore()
    node_store = NodeStore()
    
    # Get theme
    theme = theme_store.get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    
    # Get nodes
    nodes = []
    if include_nodes:
        for node_id in theme.node_ids:
            node = node_store.get(node_id)
            if node:
                nodes.append({
                    "id": node.id,
                    "proposition": node.processed.proposition,
                    "tags": node.tags,
                    "timestamp": node.timestamp.isoformat()
                })
    
    return ThemeDetailResponse(
        theme=_convert_theme_to_response(theme),
        nodes=nodes
    )


@router.post("/query/themes", response_model=AggregatedSearchResponse)
async def aggregated_theme_search(
    request: dict,
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Search with theme aggregation.
    
    Returns results grouped by themes, implementing many-to-one aggregation
    where multiple nodes sharing the same theme are grouped together.
    
    Supports LLM-based semantic reranking for better search quality.
    """
    try:
        anchor = request.get("anchor", "")
        modifiers_data = request.get("modifiers", {})
        use_llm_rerank = modifiers_data.get("use_llm_rerank", True)  # Default to using LLM
        
        if not anchor:
            raise HTTPException(status_code=400, detail="Query anchor is required")
        
        # Get all themes first
        theme_store = ThemeStore()
        node_store = NodeStore()
        all_themes = theme_store.get_all_themes()
        
        # Return empty if no themes
        if not all_themes:
            return AggregatedSearchResult(
                anchor=anchor,
                query=anchor,
                results={},
                total_themes=0,
                total_nodes=0,
                modifiers=modifiers_data
            )
        
        # Apply tag filtering first if specified
        selected_tags = modifiers_data.get("tags", [])
        if selected_tags:
            filtered_themes = [t for t in all_themes if t.tag in selected_tags]
        else:
            filtered_themes = all_themes
        
        # Use LLM reranking if enabled
        if use_llm_rerank and settings.minimax_api_key:
            try:
                reranker = LLMSearchReranker()
                filters = {
                    "time_range": modifiers_data.get("time_range", "all"),
                    "tags": selected_tags
                }
                # LLM reranking (uses curl subprocess internally)
                matched_themes = reranker.rerank_themes(anchor, filtered_themes, filters)
            except Exception as e:
                # Fallback to traditional search if LLM fails
                import traceback
                print(f"[LLM Search Error] {e}")
                traceback.print_exc()
                matched_themes = _traditional_theme_search(anchor, filtered_themes)
        else:
            # Use traditional search method
            matched_themes = _traditional_theme_search(anchor, filtered_themes)
        
        # LLM 已经筛选过相关主题，不再用相似度阈值二次过滤
        # 只限制返回数量
        
        # Limit results
        limit = modifiers_data.get("limit", 20)
        matched_themes = matched_themes[:limit]
        
        # Group by tags
        tag_order = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]
        tag_display_names = {
            "definitive": "明确结论",
            "inferred": "推断结论", 
            "vague": "模糊感知",
            "needs_thinking": "待思考问题",
            "cross-domain": "跨域连接"
        }
        
        # Group themes by tag
        grouped_themes: dict[str, list] = {}
        for tag in tag_order:
            grouped_themes[tag] = []
        
        for theme, similarity in matched_themes:
            if theme.tag in grouped_themes:
                # Get full node details for this theme
                nodes = []
                for node_id in theme.node_ids:
                    node = node_store.get(node_id)
                    if node:
                        nodes.append({
                            "id": node.id,
                            "proposition": node.processed.proposition,
                            "similarity": similarity,  # Use theme similarity
                            "timestamp": node.timestamp.isoformat()
                        })
                
                if nodes:  # Only include themes with valid nodes
                    grouped_themes[theme.tag].append({
                        "theme": _convert_theme_to_response(theme),
                        "nodes": nodes,
                        "match_score": similarity
                    })
        
        # Also search for nodes that don't have themes yet
        # Execute vector search for additional nodes
        modifiers = QueryModifiers(
            time_range=modifiers_data.get("time_range", "all"),
            tags=selected_tags,
            limit=limit,
            min_similarity=min_similarity
        )
        
        node_results = await query_engine.search(
            anchor=anchor,
            modifiers=modifiers
        )
        
        # Find nodes not already covered by themes
        covered_node_ids = set()
        for theme_list in grouped_themes.values():
            for theme_data in theme_list:
                for node in theme_data["nodes"]:
                    covered_node_ids.add(node["id"])
        
        # Add uncovered nodes as individual "themes"
        for result in node_results:
            if result.node.id not in covered_node_ids:
                tag = result.node.tags[0] if result.node.tags else "vague"
                if tag in grouped_themes:
                    grouped_themes[tag].append({
                        "theme": {
                            "id": f"node-{result.node.id}",
                            "summary": result.node.processed.proposition[:500],
                            "tag": tag,
                            "node_count": 1,
                            "keywords": [],
                            "node_ids": [result.node.id]
                        },
                        "nodes": [{
                            "id": result.node.id,
                            "proposition": result.node.processed.proposition,
                            "similarity": result.similarity,
                            "timestamp": result.node.timestamp.isoformat()
                        }],
                        "match_score": result.similarity
                    })
        
        # Build final response
        aggregated_results = []
        for tag in tag_order:
            themes = grouped_themes.get(tag, [])
            if themes:
                # Sort themes within each tag by match score
                themes.sort(key=lambda x: x["match_score"], reverse=True)
                
                aggregated_results.append({
                    "tag": tag,
                    "tag_display_name": tag_display_names[tag],
                    "themes": themes,
                    "total_count": len(themes)
                })
        
        return AggregatedSearchResponse(
            query=anchor,
            total_themes=sum(len(r["themes"]) for r in aggregated_results),
            results=aggregated_results
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/themes/extract")
async def extract_themes_from_node(
    node_id: str,
    background: bool = Query(default=False, description="Run in background")
):
    """Extract themes from a specific node.
    
    This endpoint can be called to manually trigger theme extraction.
    """
    from rhizome.core.theme_extractor import ThemeExtractor, MockThemeExtractor
    
    node_store = NodeStore()
    theme_store = ThemeStore()
    
    # Get node
    node = node_store.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    try:
        # Use real extractor if API key is available, otherwise mock
        try:
            extractor = ThemeExtractor()
        except ValueError:
            extractor = MockThemeExtractor()
        
        # Extract themes
        import asyncio
        extracted_themes = await extractor.extract_themes_from_node(node)
        
        # Create or update themes
        created_themes = []
        for theme_data in extracted_themes:
            # Check if similar theme exists
            existing_themes = theme_store.list_themes_by_tag(theme_data["tag"])
            
            # Simple matching - check for similar summary
            matched_theme = None
            for existing in existing_themes:
                similarity = extractor._calculate_similarity(
                    existing.summary,
                    theme_data["summary"]
                )
                if similarity >= 0.7:  # Threshold for matching
                    matched_theme = existing
                    break
            
            if matched_theme:
                # Add node to existing theme
                matched_theme.add_node(node_id)
                theme_store.save_theme(matched_theme)
                created_themes.append(matched_theme)
            else:
                # Create new theme
                new_theme = Theme(
                    summary=theme_data["summary"],
                    tag=theme_data["tag"],
                    keywords=theme_data.get("keywords", []),
                    node_ids=[node_id]
                )
                theme_store.save_theme(new_theme)
                created_themes.append(new_theme)
        
        # Update node themes association
        from rhizome.core.theme_models import NodeTheme
        
        node_themes = theme_store.get_node_themes(node_id)
        if not node_themes:
            node_themes = NodeTheme(node_id=node_id)
        
        for theme in created_themes:
            if theme.id not in node_themes.theme_ids:
                node_themes.theme_ids.append(theme.id)
        
        node_themes.extracted_themes = [t["summary"] for t in extracted_themes]
        theme_store.save_node_themes(node_themes)
        
        return {
            "message": f"Extracted {len(created_themes)} themes from node",
            "node_id": node_id,
            "themes": [_convert_theme_to_response(t) for t in created_themes]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"主题提取失败: {str(e)}")
