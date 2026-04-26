"""Optimized streaming search API with caching and parallel execution."""

import json
import asyncio
import time
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from rhizome.core.theme_models import Theme
from rhizome.core.node_store import NodeStore
from rhizome.retrieval.query_engine import QueryEngine
from rhizome.api.dependencies import get_query_engine
from rhizome.retrieval.search_optimizer import get_search_optimizer

router = APIRouter()


class OptimizedSearchProgress:
    """Optimized search progress with timing info."""
    
    STAGES = {
        "submitting": {"percent": 5, "message": "正在提交搜索..."},
        "cache_check": {"percent": 10, "message": "正在检查缓存..."},
        "loading_themes": {"percent": 15, "message": "正在加载主题数据..."},
        "llm_reranking": {"percent": 25, "message": "正在等待LLM响应..."},
        "vector_search": {"percent": 60, "message": "正在执行向量搜索..."},
        "processing_results": {"percent": 85, "message": "正在处理搜索结果..."},
        "grouping": {"percent": 95, "message": "正在整理结果..."},
        "complete": {"percent": 100, "message": "搜索完成！"},
        "error": {"percent": 0, "message": "搜索出错"}
    }
    
    def __init__(self):
        self.stage = "submitting"
        self.detail = ""
        self.cache_status = None
        self.elapsed_time = 0
    
    def to_dict(self) -> dict:
        stage_info = self.STAGES.get(self.stage, self.STAGES["submitting"])
        result = {
            "type": "progress",
            "stage": self.stage,
            "percent": stage_info["percent"],
            "message": stage_info["message"],
            "detail": self.detail,
            "elapsed_ms": int(self.elapsed_time * 1000)
        }
        if self.cache_status:
            result["cache_status"] = self.cache_status
        return result
    
    def to_sse(self) -> str:
        return f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


class OptimizedStreamingSearch:
    """Optimized streaming search with caching and parallel execution."""
    
    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine
        self.optimizer = get_search_optimizer(query_engine)
        self.progress = OptimizedSearchProgress()
        self.start_time = 0
    
    async def search(
        self,
        anchor: str,
        modifiers_data: dict
    ) -> AsyncGenerator[str, None]:
        """Execute optimized streaming search."""
        
        self.start_time = time.time()
        
        try:
            # Stage 1: Submitting
            self.progress.stage = "submitting"
            yield self._send_progress()
            
            # Get parameters
            min_similarity = modifiers_data.get("min_similarity", 0.3)
            limit = modifiers_data.get("limit", 20)
            search_mode = modifiers_data.get("search_mode", "balanced")

            # Adjust min_similarity based on search mode
            mode_similarity = {
                "strict": 0.5,
                "balanced": 0.3,
                "explore": 0.1
            }
            effective_min_similarity = mode_similarity.get(search_mode, min_similarity)
            
            # Stage 2: Check cache and load themes (fast, from cache)
            self.progress.stage = "cache_check"
            yield self._send_progress()
            
            # Stage 3: Execute parallel search (LLM + Vector)
            self.progress.stage = "llm_reranking"
            self.progress.detail = "正在并行执行语义重排序和向量搜索..."
            yield self._send_progress()
            
            # Execute both searches in parallel with progress heartbeat
            search_task = asyncio.create_task(
                self.optimizer.parallel_search(anchor, modifiers_data)
            )
            
            # Wait for completion with periodic progress updates
            last_update = time.time()
            while not search_task.done():
                try:
                    # Wait for task completion with timeout
                    await asyncio.wait_for(asyncio.shield(search_task), timeout=3.0)
                except asyncio.TimeoutError:
                    # Task not done yet, send progress heartbeat
                    elapsed = time.time() - self.start_time
                    self.progress.detail = f"正在等待LLM响应... ({elapsed:.1f}s)"
                    yield self._send_progress()
                    last_update = time.time()
            
            matched_themes, vector_results, cache_status = await search_task
            
            self.progress.cache_status = cache_status
            
            if cache_status == "hit":
                self.progress.detail = f"缓存命中！找到 {len(matched_themes)} 个相关主题"
            elif cache_status == "timeout":
                self.progress.detail = f"LLM超时，使用传统搜索找到 {len(matched_themes)} 个主题"
            else:
                self.progress.detail = f"找到 {len(matched_themes)} 个相关主题"
            
            yield self._send_progress()
            
            # Stage 4: Process results
            self.progress.stage = "processing_results"
            
            # LLM 已经筛选过相关主题，不再用相似度阈值二次过滤
            # 不截断结果，让前端控制显示数量
            total_matched = len(matched_themes)
            
            self.progress.detail = f"正在处理 {total_matched} 个匹配主题..."
            yield self._send_progress()
            
            # Get node store for fetching node details
            node_store = NodeStore()
            
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
                if similarity <= 0.0:
                    continue
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
            
            # Stage 5: Add vector search results
            self.progress.stage = "vector_search"
            
            # Find uncovered nodes
            covered_node_ids = set()
            for theme_list in grouped_themes.values():
                for theme_data in theme_list:
                    for node in theme_data["nodes"]:
                        covered_node_ids.add(node["id"])
            
            # Add uncovered nodes from vector search (使用模式对应的相似度阈值)
            filtered_vector_results = [r for r in vector_results if r.similarity >= effective_min_similarity]
            vector_supplement_count = 0
            mode_limit = {"strict": 5, "balanced": 10, "explore": 20}.get(search_mode, 10)
            for result in filtered_vector_results:
                if vector_supplement_count >= mode_limit:
                    break
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
                        vector_supplement_count += 1
            
            self.progress.detail = f"向量搜索补充了 {len(filtered_vector_results)} 个相关节点"
            yield self._send_progress()
            
            # Stage 6: Grouping
            self.progress.stage = "grouping"
            self.progress.detail = "正在整理最终结果..."
            yield self._send_progress()
            
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
            
            # Stage 7: Complete
            self.progress.stage = "complete"
            total_themes = sum(r["total_count"] for r in aggregated_results)
            total_time = time.time() - self.start_time
            self.progress.detail = f"找到 {total_themes} 个主题 (耗时 {total_time:.2f}s)"
            self.progress.elapsed_time = total_time
            yield self._send_progress()
            
            # Send final result with timing info
            result = {
                "type": "result",
                "query": anchor,
                "total_themes": total_themes,
                "elapsed_ms": int(total_time * 1000),
                "cache_status": cache_status,
                "results": aggregated_results
            }
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            self.progress.stage = "error"
            self.progress.detail = str(e)
            yield self._send_progress()
            
            error_result = {
                "type": "error",
                "message": str(e),
                "elapsed_ms": int((time.time() - self.start_time) * 1000)
            }
            yield f"data: {json.dumps(error_result, ensure_ascii=False)}\n\n"
    
    def _send_progress(self) -> str:
        self.progress.elapsed_time = time.time() - self.start_time
        return self.progress.to_sse()
    
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


@router.post("/query/themes/stream/fast")
async def optimized_stream_theme_search(
    request: dict,
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """
    Optimized streaming theme search with caching and parallel execution.
    
    Optimizations:
    - Query result caching (5 min TTL)
    - Theme data caching (60 sec refresh)
    - LLM reranking + Vector search in parallel
    - LLM timeout with graceful fallback (2 min timeout for quality)
    
    This endpoint prioritizes quality while maintaining performance:
    - Cache hits: < 1 second
    - Cache misses with LLM: 10-25 seconds (parallel execution)
    - LLM timeout fallback (2 min): < 2 seconds (rarely triggered)
    
    Returns timing information in progress updates and final result.
    """
    anchor = request.get("anchor", "")
    modifiers_data = request.get("modifiers", {})
    
    if not anchor:
        raise HTTPException(status_code=400, detail="Query anchor is required")
    
    streamer = OptimizedStreamingSearch(query_engine)
    
    return StreamingResponse(
        streamer.search(anchor, modifiers_data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/search/cache/stats")
async def get_search_cache_stats(
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Get search cache statistics."""
    optimizer = get_search_optimizer(query_engine)
    return optimizer.get_cache_stats()


@router.post("/search/cache/clear")
async def clear_search_cache(
    query_engine: QueryEngine = Depends(get_query_engine)
):
    """Clear search cache."""
    optimizer = get_search_optimizer(query_engine)
    optimizer.clear_cache()
    return {"message": "Cache cleared successfully"}
