"""Search optimization module with caching and parallel execution."""

import asyncio
import hashlib
import logging
import time
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading

from rhizome.core.theme_models import Theme
from rhizome.core.theme_store import ThemeStore
from rhizome.core.node_store import NodeStore
from rhizome.retrieval.llm_search import LLMSearchReranker
from rhizome.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with timestamp and TTL."""
    query_hash: str
    results: List[Tuple[Theme, float]]
    timestamp: float
    ttl: int = 300  # 5 minutes default TTL
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


class SearchCache:
    """LRU cache for search results with TTL support."""
    
    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, query: str, tags: tuple, time_range: str, search_mode: str = "balanced") -> str:
        """Generate cache key from query parameters."""
        # Normalize tags to comma-separated sorted string for consistent keys
        tags_str = ",".join(sorted(tags)) if tags else ""
        # 包含 search_mode 在缓存键中，确保不同模式有独立缓存
        key_string = f"{query.lower().strip()}|{tags_str}|{time_range}|{search_mode}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, query: str, tags: List[str], time_range: str, search_mode: str = "balanced") -> Optional[List[Tuple[Theme, float]]]:
        """Get cached results if available and not expired."""
        key = self._generate_key(query, tuple(sorted(tags)), time_range, search_mode)
        
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            
            self._hits += 1
            return entry.results
    
    def set(self, query: str, tags: List[str], time_range: str, 
            results: List[Tuple[Theme, float]], ttl: Optional[int] = None, search_mode: str = "balanced"):
        """Cache search results."""
        key = self._generate_key(query, tuple(sorted(tags)), time_range, search_mode)
        
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self.max_size:
                oldest_key = min(self._cache.keys(), 
                               key=lambda k: self._cache[k].timestamp)
                del self._cache[oldest_key]
            
            self._cache[key] = CacheEntry(
                query_hash=key,
                results=results,
                timestamp=time.time(),
                ttl=ttl or self.default_ttl
            )
    
    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "max_size": self.max_size
            }


class ThemeDataCache:
    """Global cache for theme and node data to avoid reloading."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self):
        self._themes: Optional[List[Theme]] = None
        self._last_refresh: float = 0
        self._refresh_interval: int = 60  # Refresh every 60 seconds
        self._theme_store = ThemeStore()
        self._node_store = NodeStore()
    
    def get_themes(self, force_refresh: bool = False) -> List[Theme]:
        """Get cached themes, refresh if expired."""
        current_time = time.time()
        
        if (force_refresh or 
            self._themes is None or 
            current_time - self._last_refresh > self._refresh_interval):
            
            self._themes = self._theme_store.get_all_themes()
            self._last_refresh = current_time
        
        return self._themes
    
    def invalidate(self):
        """Invalidate cache to force refresh on next access."""
        self._themes = None
        self._last_refresh = 0
    
    def get_cache_age(self) -> float:
        """Get age of cached data in seconds."""
        if self._themes is None:
            return float('inf')
        return time.time() - self._last_refresh


class OptimizedSearch:
    """Optimized search with caching and parallel execution."""
    
    def __init__(self, query_engine):
        self.query_engine = query_engine
        self.cache = SearchCache(max_size=50, default_ttl=300)  # 5 min TTL
        self.theme_cache = ThemeDataCache()
        self.reranker: Optional[LLMSearchReranker] = None
        
        # Initialize reranker lazily
        if settings.minimax_api_key:
            try:
                self.reranker = LLMSearchReranker()
            except Exception as e:
                logger.warning(f"Failed to initialize LLM reranker: {e}")
    
    async def search_with_timeout(
        self,
        anchor: str,
        modifiers_data: dict,
        llm_timeout: float = 120.0  # 2 minute timeout for LLM - ensures quality results
    ) -> Tuple[List[Tuple[Theme, float]], Optional[str]]:
        """
        Execute optimized search with timeout and caching.
        
        Returns:
            Tuple of (matched_themes, cache_status)
            cache_status: "hit", "miss", "timeout", "error", or None
        """
        selected_tags = modifiers_data.get("tags", [])
        time_range = modifiers_data.get("time_range", "all")
        use_llm = modifiers_data.get("use_llm_rerank", True)
        search_mode = modifiers_data.get("search_mode", "balanced")
        
        logger.info(f"[LLM Search] Starting search for: '{anchor}'")
        logger.info(f"[LLM Search] use_llm={use_llm}, reranker_exists={self.reranker is not None}, api_key_exists={bool(settings.minimax_api_key)}")
        logger.info(f"[LLM Search] selected_tags={selected_tags}, time_range={time_range}, search_mode={search_mode}")
        
        # Try cache first
        cached_results = self.cache.get(anchor, selected_tags, time_range, search_mode)
        if cached_results is not None:
            logger.info(f"[LLM Search] Cache hit for '{anchor}'")
            return cached_results, "hit"
        
        # Get themes from cache
        all_themes = self.theme_cache.get_themes()
        logger.info(f"[LLM Search] Loaded {len(all_themes)} themes from cache")
        
        # Filter themes by tags
        if selected_tags:
            filtered_themes = [t for t in all_themes if t.tag in selected_tags]
            logger.info(f"[LLM Search] After tag filtering: {len(filtered_themes)} themes (selected_tags={selected_tags})")
        else:
            filtered_themes = all_themes

        # Filter themes by time range
        if time_range and time_range != "all":
            from datetime import datetime, timedelta
            now = datetime.now()
            if time_range == "last_week":
                cutoff = now - timedelta(days=7)
            elif time_range == "last_month":
                cutoff = now - timedelta(days=30)
            elif time_range == "last_3_months":
                cutoff = now - timedelta(days=90)
            else:
                cutoff = None

            if cutoff:
                original_count = len(filtered_themes)
                filtered_themes = [t for t in filtered_themes if t.created_at >= cutoff]
                logger.info(f"[LLM Search] After time filtering ({time_range}): {len(filtered_themes)} themes (filtered {original_count - len(filtered_themes)})")

        logger.info(f"[LLM Search] Final filtered themes: {len(filtered_themes)}")
        
        if not filtered_themes:
            logger.warning(f"[LLM Search] No themes available after filtering")
            return [], None
        
        # Try LLM with timeout
        if use_llm and self.reranker and settings.minimax_api_key:
            logger.info(f"[LLM Search] Attempting LLM reranking for '{anchor}' with {len(filtered_themes)} themes")
            try:
                # Run LLM reranking with timeout
                logger.info(f"[LLM Search] Calling LLM API (timeout={llm_timeout}s)...")
                matched_themes = await asyncio.wait_for(
                    self._async_rerank(anchor, filtered_themes, time_range, search_mode, selected_tags),
                    timeout=llm_timeout
                )
                
                logger.info(f"[LLM Search] LLM reranking successful, got {len(matched_themes)} results")

                # Enforce per-mode result limits (LLM may not follow prompt instructions)
                matched_themes = self._apply_mode_limit(matched_themes, search_mode)

                # Cache successful results
                self.cache.set(anchor, selected_tags, time_range, matched_themes, search_mode=search_mode)
                return matched_themes, "miss"

            except asyncio.TimeoutError:
                # LLM timeout - fall back to traditional search
                logger.warning(f"[LLM Search] LLM timeout after {llm_timeout}s, falling back to traditional search")
                matched_themes = self._traditional_search(anchor, filtered_themes)
                matched_themes = self._apply_mode_limit(matched_themes, search_mode)
                # Cache fallback results with shorter TTL (2 min)
                self.cache.set(anchor, selected_tags, time_range, matched_themes, ttl=120, search_mode=search_mode)
                return matched_themes, "timeout"

            except Exception as e:
                # LLM error - fall back to traditional search
                logger.error(f"[LLM Search] LLM error: {e}, falling back to traditional search")
                import traceback
                logger.error(f"[LLM Search] Traceback: {traceback.format_exc()}")
                matched_themes = self._traditional_search(anchor, filtered_themes)
                matched_themes = self._apply_mode_limit(matched_themes, search_mode)
                # Cache fallback results with shorter TTL (2 min)
                self.cache.set(anchor, selected_tags, time_range, matched_themes, ttl=120, search_mode=search_mode)
                return matched_themes, "error"
        else:
            # No LLM available, use traditional search
            reason = []
            if not use_llm:
                reason.append("use_llm=False")
            if not self.reranker:
                reason.append("reranker=None")
            if not settings.minimax_api_key:
                reason.append("no_api_key")
            logger.warning(f"[LLM Search] LLM not available ({', '.join(reason)}), using traditional search")
            matched_themes = self._traditional_search(anchor, filtered_themes)
            matched_themes = self._apply_mode_limit(matched_themes, search_mode)
            # Cache traditional search results with shorter TTL (3 min)
            self.cache.set(anchor, selected_tags, time_range, matched_themes, ttl=180, search_mode=search_mode)
            return matched_themes, None
    
    async def _async_rerank(
        self,
        anchor: str,
        themes: List[Theme],
        time_range: str,
        search_mode: str = "balanced",
        selected_tags: List[str] = None
    ) -> List[Tuple[Theme, float]]:
        """Async wrapper for LLM reranking."""
        loop = asyncio.get_event_loop()

        def _rerank():
            filters = {
                "time_range": time_range,
                "tags": selected_tags or [],
                "search_mode": search_mode
            }
            logger.info(f"[LLM Search] Filters passed to LLM: {filters}")
            return self.reranker.rerank_themes(anchor, themes, filters)

        return await loop.run_in_executor(None, _rerank)
    
    def _traditional_search(
        self,
        anchor: str,
        themes: List[Theme]
    ) -> List[Tuple[Theme, float]]:
        """Fast traditional keyword-based search."""
        from rhizome.core.theme_extractor import ThemeExtractor
        extractor = ThemeExtractor()
        
        anchor_lower = anchor.lower()
        anchor_words = set(anchor_lower.split())
        theme_scores = []
        
        for theme in themes:
            theme_summary_lower = theme.summary.lower()
            
            # Quick exact match check
            if anchor_lower in theme_summary_lower:
                similarity = 0.95
            else:
                # Word overlap calculation
                theme_words = set(theme_summary_lower.split())
                if anchor_words and theme_words:
                    overlap = len(anchor_words & theme_words)
                    similarity = overlap / max(len(anchor_words), len(theme_words)) * 0.85
                else:
                    similarity = 0.0
            
            # Boost for keyword matches
            keyword_boost = sum(0.1 for kw in theme.keywords if kw.lower() in anchor_lower)
            similarity = min(similarity + keyword_boost, 1.0)
            
            theme_scores.append((theme, similarity))
        
        # Filter out zero-score themes and sort by similarity
        theme_scores = [(t, s) for t, s in theme_scores if s > 0.0]
        theme_scores.sort(key=lambda x: x[1], reverse=True)
        return theme_scores
    
    def _apply_mode_limit(
        self,
        themes: List[Tuple[Theme, float]],
        search_mode: str
    ) -> List[Tuple[Theme, float]]:
        """Truncate results to per-mode limits."""
        mode_limits = {
            "strict": 5,
            "balanced": 10,
            "explore": 20
        }
        max_results = mode_limits.get(search_mode, 10)
        if len(themes) > max_results:
            return themes[:max_results]
        return themes

    async def parallel_search(
        self,
        anchor: str,
        modifiers_data: dict
    ) -> Tuple[List[Tuple[Theme, float]], list, Optional[str]]:
        """
        Execute theme search and vector search in parallel.
        
        Returns:
            Tuple of (matched_themes, vector_results, cache_status)
        """
        from rhizome.retrieval.query_engine import QueryModifiers
        
        # Start theme search
        theme_task = asyncio.create_task(
            self.search_with_timeout(anchor, modifiers_data)
        )
        
        # Start vector search in parallel
        async def _vector_search():
            modifiers = QueryModifiers(
                time_range=modifiers_data.get("time_range", "all"),
                tags=modifiers_data.get("tags", []),
                limit=modifiers_data.get("limit", 20),
                min_similarity=modifiers_data.get("min_similarity", 0.3)
            )
            return await self.query_engine.search(anchor=anchor, modifiers=modifiers)
        
        vector_task = asyncio.create_task(_vector_search())
        
        # Wait for both to complete
        (matched_themes, cache_status), vector_results = await asyncio.gather(
            theme_task, vector_task
        )
        
        return matched_themes, vector_results, cache_status
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "search_cache": self.cache.get_stats(),
            "theme_cache_age_seconds": round(self.theme_cache.get_cache_age(), 1)
        }
    
    def clear_cache(self):
        """Clear all caches."""
        self.cache.clear()
        self.theme_cache.invalidate()


# Global search optimizer instance
_search_optimizer: Optional[OptimizedSearch] = None


def invalidate_theme_cache() -> None:
    """Invalidate the global theme cache to force refresh on next access.

    Call this after creating, updating, or deleting nodes.
    """
    if _search_optimizer is not None:
        _search_optimizer.theme_cache.invalidate()


def get_search_optimizer(query_engine) -> OptimizedSearch:
    """Get or create global search optimizer instance."""
    global _search_optimizer
    if _search_optimizer is None or _search_optimizer.query_engine != query_engine:
        _search_optimizer = OptimizedSearch(query_engine)
    return _search_optimizer
