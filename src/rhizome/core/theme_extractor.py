"""Theme extraction service for Rhizome Thinking.

This module uses AI to extract themes from nodes and aggregate them.
"""

import logging
from typing import Any, Optional

from rhizome.core.llm_client import LLMClient, MockLLMClient
from rhizome.core.models import Node
from rhizome.core.theme_models import Theme, NodeTheme


logger = logging.getLogger(__name__)

THEME_EXTRACTION_SYSTEM_PROMPT = """你是一个主题提取专家。你的任务是从用户的知识笔记中提取核心主题/观点。

核心原则：
1. 提取的是"主题"或"观点"，不是笔记的摘要
2. 主题应该像一个问题或一个结论，能概括多条笔记的共同内容
3. 主题要简洁明了，让人一眼就能理解这组笔记在讨论什么

主题提取规则：
1. 从每条笔记中提取1-3个核心主题
2. 主题应该是通用性的，可以涵盖多条类似笔记
3. 主题格式可以是：
   - 问题形式："如何确保AGI的安全性？"
   - 结论形式："AGI将在10年内实现"
   - 观点形式："大模型是通往AGI的主要路径"
4. 避免提取过于具体或细节化的内容

标签分类指南：
- definitive: 明确的结论或断言类主题
- inferred: 推断类、推测类主题
- vague: 模糊、尚未清晰的主题
- needs_thinking: 待思考的问题类主题
- cross-domain: 跨领域连接类主题

输出格式必须是JSON，包含提取的主题列表。"""

THEME_EXTRACTION_USER_TEMPLATE = """请从以下笔记中提取核心主题：

笔记标题：{proposition}

笔记内容：
{raw_input}

{questions_section}

标签：{tags}

请按以下JSON格式返回提取的主题：

{{
  "themes": [
    {{
      "summary": "主题摘要，20-50字，像问题或结论",
      "tag": "primary_tag",
      "keywords": ["keyword1", "keyword2"]
    }}
  ]
}}

要求：
1. 提取1-3个核心主题
2. 主题要能概括这条笔记的核心内容
3. tag必须是以下之一：definitive, inferred, vague, needs_thinking, cross-domain
4. 返回JSON格式，不要其他内容"""

THEME_MERGING_SYSTEM_PROMPT = """你是一个主题合并专家。你的任务是判断多个主题是否表达相同或高度相似的观点，应该合并为一个主题。

合并规则：
1. 如果两个主题讨论的是同一个问题/结论，即使措辞不同，也应该合并
2. 合并后的主题摘要应该更通用，能涵盖所有相关笔记
3. 保留原始主题的关键词集合
4. 不要过度合并，只有真正相似的主题才合并

示例应该合并的主题：
- "如何确保AGI安全？" 和 "AGI的安全性问题" → 合并为 "AGI的安全保障问题"
- "AGI将在10年内实现" 和 "10年内会出现AGI" → 合并为 "AGI将在10年内实现"

示例不应该合并的主题：
- "AGI安全问题" 和 "AGI的伦理问题" → 这是不同主题
- "深度学习原理" 和 "神经网络架构" → 这是不同主题

输出格式必须是JSON。"""


class ThemeExtractor(LLMClient):
    """Extracts and manages themes from nodes using AI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> None:
        """Initialize the theme extractor.

        Args:
            api_key: MiniMax API key (defaults to settings)
            base_url: MiniMax API base URL (defaults to settings)
            model: Model name (defaults to settings)
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            default_timeout=60.0,
            max_retries=3
        )

    def process_response(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Process API response into theme list.

        Args:
            response: API response dictionary

        Returns:
            List of validated theme dictionaries
        """
        data = self.parse_json_response(response)
        themes = data.get("themes", [])

        # Validate themes
        valid_tags = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]
        validated_themes = []

        for theme in themes:
            if "summary" in theme and theme["summary"]:
                # Validate tag
                tag = theme.get("tag", "vague")
                if tag not in valid_tags:
                    tag = "vague"

                validated_themes.append({
                    "summary": theme["summary"][:500],  # Limit summary length
                    "tag": tag,
                    "keywords": theme.get("keywords", [])[:5]  # Limit keywords
                })

        return validated_themes

    async def extract_themes_from_node(self, node: Node) -> list[dict[str, Any]]:
        """Extract themes from a single node.

        Args:
            node: The node to extract themes from

        Returns:
            List of extracted theme dictionaries
        """
        # Build questions section
        questions_section = ""
        if node.processed.open_questions:
            questions_section = "开放问题：\n" + "\n".join(f"- {q}" for q in node.processed.open_questions)

        # Build user prompt
        user_prompt = THEME_EXTRACTION_USER_TEMPLATE.format(
            proposition=node.processed.proposition,
            raw_input=node.raw_input[:500],  # Limit raw input length
            questions_section=questions_section,
            tags=", ".join(node.tags)
        )

        messages = [
            {"role": "system", "content": THEME_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = await self.call_api_async(messages, max_tokens=2000)
            return self.process_response(response)

        except Exception as e:
            logger.error(f"Failed to extract themes from node {node.id}: {e}")
            # Return default theme
            return [{
                "summary": node.processed.proposition[:80],
                "tag": node.tags[0] if node.tags else "vague",
                "keywords": []
            }]

    async def merge_similar_themes(
        self,
        themes: list[Theme],
        similarity_threshold: float = 0.8
    ) -> list[Theme]:
        """Merge similar themes together.

        This is a simplified implementation that uses string similarity.
        For production, consider using embedding-based similarity.

        Args:
            themes: List of themes to merge
            similarity_threshold: Threshold for considering themes similar

        Returns:
            List of merged themes
        """
        if len(themes) <= 1:
            return themes

        merged = []
        merged_indices = set()

        for i, theme1 in enumerate(themes):
            if i in merged_indices:
                continue

            # Find similar themes
            similar_themes = [theme1]
            similar_indices = [i]

            for j, theme2 in enumerate(themes[i+1:], start=i+1):
                if j in merged_indices:
                    continue

                # Simple similarity check (can be improved with embeddings)
                similarity = self._calculate_similarity(theme1.summary, theme2.summary)

                if similarity >= similarity_threshold and theme1.tag == theme2.tag:
                    similar_themes.append(theme2)
                    similar_indices.append(j)

            # Merge similar themes
            if len(similar_themes) > 1:
                merged_theme = self._merge_theme_group(similar_themes)
                merged.append(merged_theme)
                merged_indices.update(similar_indices)
            else:
                merged.append(theme1)

        return merged

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity between two texts.

        Uses Jaccard similarity on character bigrams.
        """
        def get_bigrams(text):
            text = text.lower()
            return set(text[i:i+2] for i in range(len(text) - 1))

        bigrams1 = get_bigrams(text1)
        bigrams2 = get_bigrams(text2)

        if not bigrams1 or not bigrams2:
            return 0.0

        intersection = len(bigrams1 & bigrams2)
        union = len(bigrams1 | bigrams2)

        return intersection / union if union > 0 else 0.0

    def _merge_theme_group(self, themes: list[Theme]) -> Theme:
        """Merge a group of similar themes into one.

        Args:
            themes: List of similar themes

        Returns:
            Merged theme
        """
        # Use the most common summary or the first one
        # In a more sophisticated implementation, we could use AI to generate a better summary
        best_summary = themes[0].summary

        # Collect all node IDs
        all_node_ids = []
        for theme in themes:
            all_node_ids.extend(theme.node_ids)

        # Remove duplicates while preserving order
        seen = set()
        unique_node_ids = []
        for node_id in all_node_ids:
            if node_id not in seen:
                seen.add(node_id)
                unique_node_ids.append(node_id)

        # Collect all keywords
        all_keywords = []
        for theme in themes:
            all_keywords.extend(theme.keywords)

        # Get unique keywords
        unique_keywords = list(dict.fromkeys(all_keywords))[:10]  # Limit to 10

        return Theme(
            summary=best_summary,
            tag=themes[0].tag,
            node_ids=unique_node_ids,
            keywords=unique_keywords
        )


class MockThemeExtractor(MockLLMClient):
    """Mock theme extractor for testing without API calls."""

    async def extract_themes_from_node(self, node: Node) -> list[dict[str, Any]]:
        """Return mock extracted themes."""
        # Generate themes based on node tags
        themes = []

        for tag in node.tags[:2]:  # Use up to 2 tags
            tag_names = {
                "definitive": "明确结论",
                "inferred": "推断结论",
                "vague": "模糊感知",
                "needs_thinking": "待思考问题",
                "cross-domain": "跨域连接"
            }

            themes.append({
                "summary": f"[{tag_names.get(tag, tag)}] {node.processed.proposition[:50]}...",
                "tag": tag,
                "keywords": []
            })

        if not themes:
            themes.append({
                "summary": node.processed.proposition[:80],
                "tag": "vague",
                "keywords": []
            })

        return themes
