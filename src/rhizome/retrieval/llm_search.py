"""LLM-powered semantic search reranking."""

import json
import logging
import re
from typing import Optional

from rhizome.config import settings
from rhizome.core.llm_client import LLMClient, MockLLMClient
from rhizome.core.theme_models import Theme

logger = logging.getLogger(__name__)


class LLMSearchReranker(LLMClient):
    """Uses LLM to rerank themes based on semantic relevance."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize the LLM reranker."""
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            default_timeout=120.0,
            max_retries=3
        )

        logger.info(f"[LLM Reranker] Initializing with base_url: {self.base_url}")
        logger.info(f"[LLM Reranker] API key exists: {bool(self.api_key)}")

    def process_response(self, response: dict) -> list[tuple[Theme, float]]:
        """Process API response into ranked theme list.

        Args:
            response: API response dictionary

        Returns:
            List of (theme, score) tuples
        """
        content = self.extract_content(response)
        return self._parse_ranking(content)

    def _build_prompt(self, query: str, themes: list[Theme], filters: dict) -> str:
        """Build the prompt for LLM reranking."""
        filter_desc = []
        if filters.get("time_range") and filters["time_range"] != "all":
            time_map = {
                "last_week": "最近一周",
                "last_month": "最近一月",
                "last_3_months": "最近三月"
            }
            filter_desc.append(f"时间范围: {time_map.get(filters['time_range'], filters['time_range'])}")
        if filters.get("tags"):
            tag_names = {
                "definitive": "明确结论",
                "inferred": "推断结论",
                "vague": "模糊感知",
                "needs_thinking": "待思考问题",
                "cross-domain": "跨域连接"
            }
            tag_display = [tag_names.get(t, t) for t in filters["tags"]]
            filter_desc.append(f"分类标签: {', '.join(tag_display)}")

        filter_text = "\n".join(filter_desc) if filter_desc else "无额外筛选条件"

        # 获取搜索模式
        search_mode = filters.get("search_mode", "balanced")

        # 根据搜索模式调整提示词
        mode_instructions = {
            "strict": """严格匹配模式：
- 只选择那些直接回答搜索问题或高度相关的主题
- 主题必须与搜索词有明确的语义关联
- 宁可少选，不要错选
- 返回2-5个最精确的结果""",
            "balanced": """平衡匹配模式：
- 选择与搜索词相关的主题，包括直接相关和有一定关联的内容
- 平衡精确度和召回率
- 返回5-10个相关结果""",
            "explore": """探索模式：
- 广泛选择所有可能与搜索词相关的主题
- 包括弱相关、间接相关、背景信息类的内容
- 宁可多选，帮助用户发现潜在关联
- 返回8-15个结果，甚至可以包括看起来有微弱联系的主题"""
        }

        mode_instruction = mode_instructions.get(search_mode, mode_instructions["balanced"])

        theme_list = []
        for i, theme in enumerate(themes, 1):
            tag_names = {
                "definitive": "明确结论",
                "inferred": "推断结论",
                "vague": "模糊感知",
                "needs_thinking": "待思考问题",
                "cross-domain": "跨域连接"
            }
            tag_display = tag_names.get(theme.tag, theme.tag)
            theme_list.append(f"[{i}] {theme.summary} ({tag_display})")

        prompt = f"""你是一个智能知识库搜索助手。请根据用户的搜索词，从候选主题中找出相关的主题并排序。

搜索词: "{query}"

筛选条件: {filter_text}

匹配模式说明:
{mode_instruction}

候选主题列表（共{len(themes)}个）：

{chr(10).join(theme_list)}

请根据上述匹配模式，返回与搜索词相关的主题编号，按相关性从高到低排序。

只返回JSON格式：{{"ranking": [编号1, 编号2, ...]}}"""

        return prompt

    def rerank_themes(
        self,
        query: str,
        themes: list[Theme],
        filters: Optional[dict] = None
    ) -> list[tuple[Theme, float]]:
        """Rerank themes using LLM via httpx."""
        if not themes:
            logger.warning("[LLM Reranker] No themes to rerank")
            return []

        filters = filters or {}
        prompt = self._build_prompt(query, themes, filters)

        logger.info(f"[LLM Reranker] Reranking {len(themes)} themes for query: '{query}'")
        logger.info(f"[LLM Reranker] Using model: {settings.minimax_model}")
        logger.info(f"[LLM Reranker] Filters received: time_range={filters.get('time_range')}, tags={filters.get('tags')}, search_mode={filters.get('search_mode')}")
        logger.info(f"[LLM Reranker] Prompt preview:\n{prompt[:500]}...")

        messages = [
            {"role": "system", "content": "你是一个专门用于知识库语义搜索排序的AI助手。"},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"[LLM Reranker] Sending request to: {self.base_url}/chat/completions")

        try:
            # Use inherited sync API call method
            response = self.call_api_sync(messages, max_tokens=1000)

            logger.info("[LLM Reranker] API response received successfully")

            # Use inherited response processing
            result = self.process_response(response)
            logger.info(f"[LLM Reranker] Parsed {len(result)} ranked themes")
            return result

        except Exception as e:
            logger.error(f"[LLM Reranker] Unexpected error: {e}")
            import traceback
            logger.error(f"[LLM Reranker] Traceback: {traceback.format_exc()}")
            raise

    def _parse_ranking(self, content: str, themes: list[Theme]) -> list[tuple[Theme, float]]:
        """Parse LLM response to get ranked themes."""
        theme_by_index = {i + 1: theme for i, theme in enumerate(themes)}

        logger.info(f"[LLM Reranker] Parsing response content: {content[:500]}...")

        try:
            json_match = re.search(r'\{[^}]*"ranking"[^}]*\}', content, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)

            if json_match:
                result = json.loads(json_match.group(0))
                ranking = result.get("ranking", [])
                logger.info(f"[LLM Reranker] Parsed ranking: {ranking}")

                ranked_themes = []
                seen_indices = set()

                for idx in ranking:
                    try:
                        theme_idx = int(idx)
                        if theme_idx in theme_by_index and theme_idx not in seen_indices:
                            theme = theme_by_index[theme_idx]
                            # 根据位置分配分数，越靠前分数越高
                            score = max(0.9 - (len(ranked_themes) * 0.05), 0.3)
                            ranked_themes.append((theme, score))
                            seen_indices.add(theme_idx)
                    except (ValueError, TypeError):
                        continue

                return ranked_themes if ranked_themes else []

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"[LLM Reranker] Failed to parse LLM response: {e}")
            raise

        logger.warning("[LLM Reranker] No JSON found in LLM response")
        raise ValueError("No JSON found in LLM response")


class MockLLMSearchReranker(MockLLMClient):
    """Mock reranker for testing without API calls."""

    def rerank_themes(
        self,
        query: str,
        themes: list[Theme],
        filters: Optional[dict] = None
    ) -> list[tuple[Theme, float]]:
        """Return themes in original order with dummy scores."""
        return [(theme, 0.5) for theme in themes]
