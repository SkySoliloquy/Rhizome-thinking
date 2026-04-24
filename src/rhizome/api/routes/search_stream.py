"""Streaming search API with progress updates using SSE."""

import json
import asyncio
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rhizome.core.theme_models import Theme
from rhizome.core.theme_store import ThemeStore
from rhizome.core.node_store import NodeStore
from rhizome.retrieval.query_engine import QueryEngine, QueryModifiers
from rhizome.retrieval.llm_search import LLMSearchReranker, MockLLMSearchReranker
from rhizome.api.dependencies import get_query_engine
from rhizome.config import settings

router = APIRouter()


class SearchProgress:
    """Search progress state and messaging."""
    
    STAGES = {
        "submitting": {"percent": 5, "message": "正在提交搜索..."},
        "loading_themes": {"percent": 10, "message": "正在加载主题数据..."},
        "filtering": {"percent": 15, "message": "正在应用筛选条件..."},
        "llm_reranking": {"percent": 20, "message": "正在等待LLM响应（这可能需要10-20秒）..."},
        "processing_results": {"percent": 80, "message": "正在处理搜索结果..."},
        "vector_search": {"percent": 85, "message": "正在搜索相关节点..."},
        "grouping": {"percent": 95, "message": "正在整理结果..."},
        "complete": {"percent": 100, "message": "搜索完成！"},
        "error": {"percent": 0, "message": "搜索出错"}
    }
    
    def __init__(self):
        self.stage = "submitting"
        self.detail = ""
        self.result = None
    
    def to_dict(self) -> dict:
        stage_info = self.STAGES.get(self.stage, self.STAGES["submitting"])
        return {
            "type": "progress",
            "stage": self.stage,
            "percent": stage_info["percent"],
            "message": stage_info["message"],
            "detail": self.detail
        }
    
    def to_sse(self) -> str:
        return f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


class StreamingThemeSearch:
    """Handles streaming theme search with progress updates."""
    
    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine
        self.progress = SearchProgress()
    
    async def search(
        self,
        anchor: str,
        modifiers_data: dict
    ) -> AsyncGenerator[str, None]:
        """Execute streaming search with progress updates."""
        
        try:
            # Stage 1: Submitting
            self.progress.stage = "submitting"
            yield self.progress.to_sse()
            await asyncio.sleep(0.1)
            
            # Get parameters
            use_llm_rerank = modifiers_data.get("use_llm_rerank", True)
            selected_tags = modifiers_data.get("tags", [])
            min_similarity = modifiers_data.get("min_similarity", 0.1)
            limit = modifiers_data.get("limit", 20)
            
            # Stage 2: Loading themes
            self.progress.stage = "loading_themes"
            self.progress.detail = f"正在加载知识库主题..."
            yield self.progress.to_sse()
            
            theme_store = ThemeStore()
            node_store = NodeStore()
            all_themes = theme_store.get_all_themes()
            
            if not all_themes:
                self.progress.stage = "complete"
                self.progress.detail = "知识库为空"
                result = {
                    "type": "result",
                    "query": anchor,
                    "total_themes": 0,
                    "results": []
                }
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                return
            
            self.progress.detail = f"已加载 {len(all_themes)} 个主题"
            yield self.progress.to_sse()
            await asyncio.sleep(0.1)
            
            # Stage 3: Filtering
            self.progress.stage = "filtering"
            if selected_tags:
                self.progress.detail = f"正在按标签筛选: {', '.join(selected_tags)}"
                filtered_themes = [t for t in all_themes if t.tag in selected_tags]
            else:
                filtered_themes = all_themes
            self.progress.detail = f"筛选后剩余 {len(filtered_themes)} 个主题"
            yield self.progress.to_sse()
            await asyncio.sleep(0.1)
            
            # Stage 4: LLM Reranking (most time-consuming)
            self.progress.stage = "llm_reranking"
            self.progress.detail = "正在调用MiniMax API进行语义重排序..."
            yield self.progress.to_sse()
            
            if use_llm_rerank and settings.minimax_api_key:
                try:
                    reranker = LLMSearchReranker()
                    filters = {
                        "time_range": modifiers_data.get("time_range", "all"),
                        "tags": selected_tags
                    }
                    # This is the slow part - LLM API call
                    matched_themes = reranker.rerank_themes(anchor, filtered_themes, filters)
                    self.progress.detail = f"LLM重排序完成，找到 {len(matched_themes)} 个相关主题"
                except Exception as e:
                    # Fallback to traditional search
                    self.progress.detail = f"LLM重排序失败，使用传统搜索: {str(e)}"
                    yield self.progress.to_sse()
                    matched_themes = self._traditional_theme_search(anchor, filtered_themes)
            else:
                matched_themes = self._traditional_theme_search(anchor, filtered_themes)
                self.progress.detail = f"传统搜索完成，找到 {len(matched_themes)} 个相关主题"
            
            yield self.progress.to_sse()
            
            # Stage 5: Processing results
            self.progress.stage = "processing_results"
            
            # LLM 已经筛选过相关主题，不再用相似度阈值二次过滤
            matched_themes = matched_themes[:limit]
            
            self.progress.detail = f"正在处理 {len(matched_themes)} 个匹配主题..."
            yield self.progress.to_sse()
            
            # Group by tags
            tag_order = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]
            tag_display_names = {
                "definitive": "明确结论",
                "inferred": "推断结论",
                "vague": "模糊感知",
                "needs_thinking": "待思考问题",
                "cross-domain": "跨域连接"
            }
            
            grouped_themes: dict[str, list] = {tag: [] for tag in tag_order}
            
            for theme, similarity in matched_themes:
                if theme.tag in grouped_themes:
                    nodes = []
                    for node_id in theme.node_ids:
                        node = node_store.get(node_id)
                        if node:
                            nodes.append({
                                "id": node.id,
                                "proposition": node.processed.proposition,
                                "similarity": similarity,
                                "timestamp": node.timestamp.isoformat()
                            })
                    
                    if nodes:
                        grouped_themes[theme.tag].append({
                            "theme": self._convert_theme_to_response(theme),
                            "nodes": nodes,
                            "match_score": similarity
                        })
            
            # Stage 6: Vector search for additional nodes
            self.progress.stage = "vector_search"
            self.progress.detail = "正在执行向量语义搜索..."
            yield self.progress.to_sse()
            
            modifiers = QueryModifiers(
                time_range=modifiers_data.get("time_range", "all"),
                tags=selected_tags,
                limit=limit,
                min_similarity=min_similarity
            )
            
            node_results = await self.query_engine.search(
                anchor=anchor,
                modifiers=modifiers
            )
            
            # Find uncovered nodes
            covered_node_ids = set()
            for theme_list in grouped_themes.values():
                for theme_data in theme_list:
                    for node in theme_data["nodes"]:
                        covered_node_ids.add(node["id"])
            
            # Add uncovered nodes
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
            
            # Stage 7: Grouping
            self.progress.stage = "grouping"
            self.progress.detail = "正在整理最终结果..."
            yield self.progress.to_sse()
            
            aggregated_results = []
            for tag in tag_order:
                themes = grouped_themes.get(tag, [])
                if themes:
                    themes.sort(key=lambda x: x["match_score"], reverse=True)
                    aggregated_results.append({
                        "tag": tag,
                        "tag_display_name": tag_display_names[tag],
                        "themes": themes,
                        "total_count": len(themes)
                    })
            
            # Stage 8: Complete
            self.progress.stage = "complete"
            self.progress.detail = f"找到 {sum(r['total_count'] for r in aggregated_results)} 个主题"
            yield self.progress.to_sse()
            
            # Send final result
            result = {
                "type": "result",
                "query": anchor,
                "total_themes": sum(r["total_count"] for r in aggregated_results),
                "results": aggregated_results
            }
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            self.progress.stage = "error"
            self.progress.detail = str(e)
            yield self.progress.to_sse()
            
            error_result = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_result, ensure_ascii=False)}\n\n"
    
    def _traditional_theme_search(self, anchor: str, themes: list[Theme]) -> list[tuple[Theme, float]]:
        """Traditional keyword-based theme search as fallback."""
        from rhizome.core.theme_extractor import ThemeExtractor
        extractor = ThemeExtractor()
        
        anchor_lower = anchor.lower()
        theme_scores = []
        
        for theme in themes:
            theme_summary_lower = theme.summary.lower()
            
            if anchor_lower in theme_summary_lower or theme_summary_lower in anchor_lower:
                similarity = 0.9
            else:
                anchor_words = set(anchor_lower.split())
                theme_words = set(theme_summary_lower.split())
                if anchor_words and theme_words:
                    overlap = len(anchor_words & theme_words)
                    similarity = overlap / max(len(anchor_words), len(theme_words)) * 0.8
                else:
                    similarity = 0.0
            
            if similarity < 0.3:
                jaccard_sim = extractor._calculate_similarity(theme.summary, anchor)
                similarity = max(similarity, jaccard_sim * 0.5)
            
            for kw in theme.keywords:
                if kw.lower() in anchor_lower:
                    similarity += 0.15
            
            theme_scores.append((theme, min(similarity, 1.0)))
        
        theme_scores.sort(key=lambda x: x[1], reverse=True)
        return theme_scores
    
    def _convert_theme_to_response(self, theme: Theme) -> dict:
        """Convert Theme to response dict."""
        return {
            "id": theme.id,
            "summary": theme.summary,
            "tag": theme.tag,
            "node_count": len(theme.node_ids),
            "keywords": theme.keywords,
            "node_ids": theme.node_ids,
            "created_at": theme.created_at.isoformat(),
            "updated_at": theme.updated_at.isoformat()
        }


@router.post("/query/themes/stream")
async def stream_theme_search(
    request: dict,
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Stream theme search results with progress updates using SSE.
    
    This endpoint provides real-time progress updates during the search process:
    - submitting: Query received
    - loading_themes: Loading theme data
    - filtering: Applying tag/time filters
    - llm_reranking: Waiting for LLM response (10-20s)
    - processing_results: Processing matched themes
    - vector_search: Executing vector semantic search
    - grouping: Organizing final results
    - complete: Search finished
    
    Client should use EventSource to receive updates:
    ```javascript
    const eventSource = new EventSource('/api/v1/query/themes/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
            updateProgress(data.percent, data.message);
        } else if (data.type === 'result') {
            displayResults(data.results);
            eventSource.close();
        }
    };
    ```
    """
    anchor = request.get("anchor", "")
    modifiers_data = request.get("modifiers", {})
    
    if not anchor:
        raise HTTPException(status_code=400, detail="Query anchor is required")
    
    streamer = StreamingThemeSearch(query_engine)
    
    return StreamingResponse(
        streamer.search(anchor, modifiers_data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
