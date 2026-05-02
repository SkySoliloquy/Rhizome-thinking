"""AI-powered relationship management for Rhizome Thinking."""

import json
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rhizome.config import settings
from rhizome.core.models import Link, Node, RelationType
from rhizome.core.relationship_models import (
    RelationshipBatch,
    RelationshipStats,
    RelationshipSuggestion,
    SuggestionStatus,
    TargetType,
)
from rhizome.core.relationship_store import RelationshipStore
from rhizome.core.theme_models import Theme


RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT = """你是一个知识关系分析专家。你的任务是分析知识节点之间的潜在关系。

关系类型定义：
- support: 支持/证实。源节点的内容支持或证实目标节点的观点。
- contradict: 矛盾/反驳。源节点的内容与目标节点相矛盾或反驳。
- extend: 延伸/发展。源节点是目标节点的延伸、发展或深化。
- source: 来源/基础。源节点是目标节点的信息来源或基础。
- analogy: 类比/相似。两个节点之间存在类比关系或相似性。

分析原则：
1. 基于内容的语义相似性和逻辑关系进行判断
2. 评估关系的强度（0.0-1.0）
3. 评估你对判断的置信度（0.0-1.0）
4. 为每个建议的关系提供清晰的解释

置信度评估：
- 0.9-1.0: 明确的关系，有直接的文本证据
- 0.7-0.9: 较强的关系，有合理的推断
- 0.5-0.7: 可能的关系，基于相似性
- 0.3-0.5: 弱关系，仅供参考
- 0.0-0.3: 不太可能的关系

注意：只有置信度 >= 0.5 的关系才会被采纳。"""

RELATIONSHIP_ANALYSIS_USER_TEMPLATE = """请分析以下知识节点之间的潜在关系：

【源节点】
标题：{source_proposition}
标签：{source_tags}
内容：{source_content}

【候选节点列表】
{candidates_text}

请分析源节点与每个候选节点之间的关系，按以下JSON格式返回：

{{
  "relationships": [
    {{
      "target_index": 0,
      "target_type": "node",
      "relation_type": "support|contradict|extend|source|analogy",
      "strength": 0.8,
      "confidence": 0.85,
      "reason": "详细解释为什么这两个节点存在这种关系"
    }}
  ]
}}

要求：
1. 只返回置信度 >= 0.5 的关系
2. 每个候选节点最多返回一个最佳关系类型
3. strength 和 confidence 都要在 0.0-1.0 之间
4. reason 必须清晰说明判断依据
5. 如果没有明确关系，返回空数组"""

THEME_RELATIONSHIP_ANALYSIS_TEMPLATE = """请分析以下知识节点与主题之间的潜在关系：

【源节点】
标题：{source_proposition}
标签：{source_tags}
内容：{source_content}

【候选主题列表】
{candidates_text}

请分析源节点与每个候选主题之间的关系，按以下JSON格式返回：

{{
  "relationships": [
    {{
      "target_index": 0,
      "target_type": "theme",
      "relation_type": "support|contradict|extend|source|analogy",
      "strength": 0.8,
      "confidence": 0.85,
      "reason": "详细解释为什么这个节点与该主题存在这种关系"
    }}
  ]
}}

要求：
1. 只返回置信度 >= 0.5 的关系
2. 每个候选主题最多返回一个最佳关系类型
3. strength 和 confidence 都要在 0.0-1.0 之间
4. reason 必须清晰说明判断依据"""

REVIEW_EXISTING_RELATIONSHIPS_PROMPT = """你是一个知识库维护专家。你的任务是审查现有节点之间的关系，发现缺失的关系或错误的关系。

分析任务：
1. 审查已有连接是否合理
2. 发现潜在但未建立的关系
3. 识别可能错误的关系建议

输出格式：
{{
  "suggestions": [
    {{
      "source_index": 0,
      "target_index": 1,
      "target_type": "node",
      "relation_type": "support|contradict|extend|source|analogy",
      "strength": 0.75,
      "confidence": 0.80,
      "reason": "解释为什么应该建立这个关系",
      "is_new": true
    }}
  ]
}}

is_new: true 表示这是一个新发现的关系，false 表示这是对已有关系的修正建议"""


class RelationshipManager:
    """Manages AI-powered relationship discovery and suggestions."""

    def __init__(
        self,
        store: Optional[RelationshipStore] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Initialize the relationship manager.

        Args:
            store: RelationshipStore instance
            api_key: MiniMax API key
            base_url: MiniMax API base URL
            model: Model name
        """
        self.store = store or RelationshipStore()
        self.api_key = api_key or settings.minimax_api_key
        self.base_url = base_url or settings.minimax_base_url
        self.model = model or settings.minimax_model

        if not self.api_key:
            raise ValueError("MiniMax API key is required for relationship analysis.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_api(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call MiniMax API with retry logic."""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Use standard OpenAI message format
        openai_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            openai_messages.append({"role": role, "content": content})

        payload = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": 0.3,
            "max_tokens": 4000,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _parse_json_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse API response and extract JSON data."""
        try:
            # Check for MiniMax error response
            base_resp = response.get("base_resp", {})
            if base_resp.get("status_code", 0) != 0:
                raise ValueError(f"MiniMax API error: {base_resp.get('status_msg', 'Unknown error')}")

            # Get content
            content = response.get("reply", "")

            # Fallback to OpenAI format
            if not content:
                choices = response.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")

            if not content:
                raise ValueError("Empty content in API response")

            # Extract JSON from content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from API response: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse API response: {e}")

    async def analyze_new_node(
        self,
        node: Node,
        all_nodes: list[Node],
        all_themes: list[Theme],
        max_candidates: int = 20,
    ) -> list[RelationshipSuggestion]:
        """Analyze a new node and suggest relationships.

        Args:
            node: The new node to analyze
            all_nodes: List of all existing nodes
            all_themes: List of all themes
            max_candidates: Maximum number of candidates to analyze

        Returns:
            List of relationship suggestions
        """
        suggestions = []

        # Analyze relationships with other nodes
        if all_nodes:
            # Filter out the source node itself
            candidate_nodes = [n for n in all_nodes if n.id != node.id]
            # Limit candidates
            candidate_nodes = candidate_nodes[:max_candidates]

            node_suggestions = await self._analyze_node_relationships(
                node, candidate_nodes
            )
            suggestions.extend(node_suggestions)

        # Analyze relationships with themes
        if all_themes:
            theme_candidates = all_themes[:max_candidates // 2]
            theme_suggestions = await self._analyze_theme_relationships(
                node, theme_candidates
            )
            suggestions.extend(theme_suggestions)

        # Save suggestions as a batch
        if suggestions:
            batch = RelationshipBatch(
                node_id=node.id,
                suggestions=suggestions,
            )
            self.store.save_batch(batch)

        return suggestions

    async def _analyze_node_relationships(
        self,
        source_node: Node,
        candidate_nodes: list[Node],
    ) -> list[RelationshipSuggestion]:
        """Analyze relationships between a source node and candidate nodes."""
        if not candidate_nodes:
            return []

        # Build candidates text
        candidates_text = "\n\n".join(
            f"[{i}] {n.processed.proposition}\n标签: {', '.join(n.tags)}"
            for i, n in enumerate(candidate_nodes)
        )

        # Build prompt
        user_prompt = RELATIONSHIP_ANALYSIS_USER_TEMPLATE.format(
            source_proposition=source_node.processed.proposition,
            source_tags=", ".join(source_node.tags),
            source_content=source_node.raw_input[:500],
            candidates_text=candidates_text,
        )

        messages = [
            {"role": "system", "content": RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self._call_api(messages)
            data = self._parse_json_response(response)

            suggestions = []
            for rel in data.get("relationships", []):
                try:
                    target_idx = rel.get("target_index", 0)
                    if target_idx < 0 or target_idx >= len(candidate_nodes):
                        continue

                    target_node = candidate_nodes[target_idx]

                    suggestion = RelationshipSuggestion(
                        source_id=source_node.id,
                        target_id=target_node.id,
                        target_type="node",
                        relation_type=rel.get("relation_type", "analogy"),
                        strength=rel.get("strength", 0.5),
                        reason=rel.get("reason", ""),
                        confidence=rel.get("confidence", 0.5),
                        source_proposition=source_node.processed.proposition[:100],
                        target_proposition=target_node.processed.proposition[:100],
                    )

                    # Only include if confidence >= 0.5
                    if suggestion.confidence >= 0.5:
                        suggestions.append(suggestion)

                except (KeyError, IndexError, ValueError) as e:
                    print(f"Skipping invalid relationship suggestion: {e}")
                    continue

            return suggestions

        except Exception as e:
            print(f"Failed to analyze node relationships: {e}")
            return []

    async def _analyze_theme_relationships(
        self,
        source_node: Node,
        candidate_themes: list[Theme],
    ) -> list[RelationshipSuggestion]:
        """Analyze relationships between a source node and candidate themes."""
        if not candidate_themes:
            return []

        # Build candidates text
        candidates_text = "\n\n".join(
            f"[{i}] {t.summary}\n标签: {t.tag}\n包含{len(t.node_ids)}个节点"
            for i, t in enumerate(candidate_themes)
        )

        # Build prompt
        user_prompt = THEME_RELATIONSHIP_ANALYSIS_TEMPLATE.format(
            source_proposition=source_node.processed.proposition,
            source_tags=", ".join(source_node.tags),
            source_content=source_node.raw_input[:500],
            candidates_text=candidates_text,
        )

        messages = [
            {"role": "system", "content": RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self._call_api(messages)
            data = self._parse_json_response(response)

            suggestions = []
            for rel in data.get("relationships", []):
                try:
                    target_idx = rel.get("target_index", 0)
                    if target_idx < 0 or target_idx >= len(candidate_themes):
                        continue

                    target_theme = candidate_themes[target_idx]

                    suggestion = RelationshipSuggestion(
                        source_id=source_node.id,
                        target_id=target_theme.id,
                        target_type="theme",
                        relation_type=rel.get("relation_type", "analogy"),
                        strength=rel.get("strength", 0.5),
                        reason=rel.get("reason", ""),
                        confidence=rel.get("confidence", 0.5),
                        source_proposition=source_node.processed.proposition[:100],
                        target_proposition=target_theme.summary[:100],
                    )

                    if suggestion.confidence >= 0.5:
                        suggestions.append(suggestion)

                except (KeyError, IndexError, ValueError) as e:
                    print(f"Skipping invalid theme relationship suggestion: {e}")
                    continue

            return suggestions

        except Exception as e:
            print(f"Failed to analyze theme relationships: {e}")
            return []

    async def suggest_relationships(
        self,
        source: Node,
        candidates: list[Node],
        relation_type: Optional[RelationType] = None,
    ) -> list[RelationshipSuggestion]:
        """Suggest relationships from source to candidates.

        Args:
            source: The source node
            candidates: List of candidate target nodes
            relation_type: Optional specific relation type to look for

        Returns:
            List of relationship suggestions
        """
        suggestions = await self._analyze_node_relationships(source, candidates)

        # Filter by relation type if specified
        if relation_type:
            suggestions = [s for s in suggestions if s.relation_type == relation_type]

        return suggestions

    async def review_existing_relationships(
        self,
        all_nodes: list[Node],
        max_pairs: int = 50,
    ) -> list[RelationshipSuggestion]:
        """Review existing nodes and suggest missing relationships.

        Args:
            all_nodes: List of all nodes to review
            max_pairs: Maximum number of node pairs to analyze

        Returns:
            List of new relationship suggestions
        """
        if len(all_nodes) < 2:
            return []

        suggestions = []

        # Build existing links map for quick lookup
        existing_links = {}
        for node in all_nodes:
            for link in node.links:
                key = (node.id, link.target_id)
                existing_links[key] = link

        # Find nodes without connections that might be related
        nodes_text = "\n\n".join(
            f"[{i}] {n.processed.proposition}\n标签: {', '.join(n.tags)}\n已有连接: {len(n.links)}个"
            for i, n in enumerate(all_nodes)
        )

        user_prompt = f"""请审查以下知识节点，发现缺失的关系连接：

【节点列表】
{nodes_text}

{REVIEW_EXISTING_RELATIONSHIPS_PROMPT}

分析重点：
1. 找出内容相似但没有建立连接的对
2. 发现可能相互支持或矛盾的节点对
3. 识别可能的来源关系

限制：最多分析{max_pairs}对节点组合。"""

        messages = [
            {"role": "system", "content": RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self._call_api(messages)
            data = self._parse_json_response(response)

            for rel in data.get("suggestions", []):
                try:
                    source_idx = rel.get("source_index", 0)
                    target_idx = rel.get("target_index", 0)

                    if (
                        source_idx < 0
                        or source_idx >= len(all_nodes)
                        or target_idx < 0
                        or target_idx >= len(all_nodes)
                    ):
                        continue

                    source_node = all_nodes[source_idx]
                    target_node = all_nodes[target_idx]

                    # Skip if already connected
                    if (source_node.id, target_node.id) in existing_links:
                        continue

                    suggestion = RelationshipSuggestion(
                        source_id=source_node.id,
                        target_id=target_node.id,
                        target_type="node",
                        relation_type=rel.get("relation_type", "analogy"),
                        strength=rel.get("strength", 0.5),
                        reason=rel.get("reason", ""),
                        confidence=rel.get("confidence", 0.5),
                        source_proposition=source_node.processed.proposition[:100],
                        target_proposition=target_node.processed.proposition[:100],
                    )

                    if suggestion.confidence >= 0.5:
                        suggestions.append(suggestion)

                except (KeyError, IndexError, ValueError) as e:
                    print(f"Skipping invalid review suggestion: {e}")
                    continue

            # Save batch
            if suggestions:
                batch = RelationshipBatch(
                    node_id="review_batch",
                    suggestions=suggestions,
                    analysis_version="review_1.0",
                )
                self.store.save_batch(batch)

        except Exception as e:
            print(f"Failed to review existing relationships: {e}")

        return suggestions

    def apply_suggestion(self, suggestion_id: str) -> bool:
        """Apply a pending suggestion by confirming it.

        Args:
            suggestion_id: The suggestion ID

        Returns:
            True if successful
        """
        return self.store.update_suggestion_status(
            suggestion_id, SuggestionStatus.CONFIRMED, reviewed_by="user"
        )

    def reject_suggestion(self, suggestion_id: str) -> bool:
        """Reject a pending suggestion.

        Args:
            suggestion_id: The suggestion ID

        Returns:
            True if successful
        """
        return self.store.update_suggestion_status(
            suggestion_id, SuggestionStatus.REJECTED, reviewed_by="user"
        )

    def get_pending_suggestions(self, limit: int = 100) -> list[RelationshipSuggestion]:
        """Get pending suggestions awaiting review.

        Args:
            limit: Maximum number to return

        Returns:
            List of pending suggestions
        """
        return self.store.get_pending_suggestions(limit)

    def get_suggestions_for_node(
        self, node_id: str, status: Optional[SuggestionStatus] = None
    ) -> list[RelationshipSuggestion]:
        """Get suggestions for a specific node.

        Args:
            node_id: The node ID
            status: Optional status filter

        Returns:
            List of suggestions
        """
        return self.store.get_suggestions_for_node(node_id, status)

    def get_stats(self) -> RelationshipStats:
        """Get statistics about relationship suggestions.

        Returns:
            Statistics object
        """
        return self.store.get_stats()

    def confirm_all_pending(self, node_id: Optional[str] = None) -> int:
        """Confirm all pending suggestions.

        Args:
            node_id: Optional node ID to limit scope

        Returns:
            Number of suggestions confirmed
        """
        if node_id:
            suggestions = self.store.get_suggestions_for_node(
                node_id, SuggestionStatus.PENDING
            )
        else:
            suggestions = self.store.get_pending_suggestions()

        count = 0
        for suggestion in suggestions:
            if self.apply_suggestion(suggestion.id):
                count += 1

        return count


class MockRelationshipManager(RelationshipManager):
    """Mock relationship manager for testing without API calls."""

    def __init__(
        self,
        store: Optional[RelationshipStore] = None,
        *args,
        **kwargs,
    ) -> None:
        """Initialize mock manager without API key check."""
        self.store = store or RelationshipStore()
        self.api_key = "mock"
        self.base_url = "mock"
        self.model = "mock"

    async def analyze_new_node(
        self,
        node: Node,
        all_nodes: list[Node],
        all_themes: list[Theme],
        max_candidates: int = 20,
    ) -> list[RelationshipSuggestion]:
        """Generate mock suggestions for testing."""
        suggestions = []

        # Generate mock suggestions based on tag similarity
        for candidate in all_nodes[:5]:
            if candidate.id == node.id:
                continue

            # Check tag overlap
            common_tags = set(node.tags) & set(candidate.tags)
            if common_tags:
                relation_type = "support" if "definitive" in common_tags else "analogy"
                suggestion = RelationshipSuggestion(
                    source_id=node.id,
                    target_id=candidate.id,
                    target_type="node",
                    relation_type=relation_type,
                    strength=0.6 + len(common_tags) * 0.1,
                    reason=f"共享标签: {', '.join(common_tags)} (模拟)",
                    confidence=0.7,
                    source_proposition=node.processed.proposition[:100],
                    target_proposition=candidate.processed.proposition[:100],
                )
                suggestions.append(suggestion)

        # Save suggestions
        if suggestions:
            batch = RelationshipBatch(
                node_id=node.id,
                suggestions=suggestions,
            )
            self.store.save_batch(batch)

        return suggestions

    async def suggest_relationships(
        self,
        source: Node,
        candidates: list[Node],
        relation_type: Optional[RelationType] = None,
    ) -> list[RelationshipSuggestion]:
        """Generate mock suggestions."""
        return await self.analyze_new_node(source, candidates, [])

    async def review_existing_relationships(
        self,
        all_nodes: list[Node],
        max_pairs: int = 50,
    ) -> list[RelationshipSuggestion]:
        """Generate mock review suggestions."""
        return []
