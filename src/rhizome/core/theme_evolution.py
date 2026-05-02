"""Theme evolution management for Rhizome Thinking.

This module provides conflict detection and evolution suggestion capabilities
for themes as the knowledge base grows.
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field, field_serializer
from tenacity import retry, stop_after_attempt, wait_exponential

from rhizome.config import settings
from rhizome.core.models import Node
from rhizome.core.theme_models import Theme, ThemeVersion


class ConflictType(str, Enum):
    """Types of conflicts that can occur in theme evolution."""

    CONTENT_CONFLICT = "content_conflict"
    TAG_MISMATCH = "tag_mismatch"
    REINFORCEMENT = "reinforcement"
    OBSOLETE = "obsolete"


class SuggestionStatus(str, Enum):
    """Status of an evolution suggestion."""

    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class ThemeEvolutionSuggestion(BaseModel):
    """Suggestion for theme evolution based on conflict detection or analysis."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this suggestion"
    )
    theme_id: str = Field(
        ...,
        description="ID of the theme this suggestion applies to"
    )
    suggested_summary: Optional[str] = Field(
        default=None,
        description="Suggested new summary for the theme"
    )
    suggested_tag: Optional[str] = Field(
        default=None,
        description="Suggested new tag for the theme"
    )
    conflict_type: ConflictType = Field(
        ...,
        description="Type of conflict or evolution detected"
    )
    reason: str = Field(
        ...,
        description="Detailed explanation of why this suggestion was generated"
    )
    affected_node_ids: list[str] = Field(
        default_factory=list,
        description="IDs of nodes that triggered or are affected by this suggestion"
    )
    status: SuggestionStatus = Field(
        default=SuggestionStatus.PENDING,
        description="Current status of the suggestion"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this suggestion was created"
    )
    applied_at: Optional[datetime] = Field(
        default=None,
        description="When this suggestion was applied (if applicable)"
    )
    previous_version: Optional[int] = Field(
        default=None,
        description="Theme version before applying this suggestion"
    )

    @field_serializer("created_at", "applied_at")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


CONFLICT_DETECTION_SYSTEM_PROMPT = """你是主题冲突检测专家。你的任务是分析新笔记与现有主题之间的关系，识别可能的冲突或需要演进的情况。

冲突类型定义：
1. content_conflict（内容冲突）：新笔记的观点与主题现有内容存在矛盾或不一致
2. tag_mismatch（标签不匹配）：新笔记的标签与主题标签不一致，可能需要调整主题分类
3. reinforcement（强化确认）：新笔记强烈支持主题观点，建议保持或小幅完善主题描述
4. obsolete（过时废弃）：新笔记表明该主题的观点已过时或不再适用

分析原则：
1. 仔细阅读主题摘要和相关笔记内容
2. 对比新笔记的核心观点与主题表述
3. 判断是否存在实质性冲突或需要调整
4. 提供具体的理由说明

输出必须是JSON格式，包含检测到的冲突列表。如果没有冲突，返回空列表。"""

CONFLICT_DETECTION_USER_TEMPLATE = """请分析以下新笔记与现有主题的潜在冲突：

新笔记：
- 标题：{node_proposition}
- 内容：{node_raw_input}
- 标签：{node_tags}

现有主题：
{themes_info}

请按以下JSON格式返回分析结果：

{{
  "conflicts": [
    {{
      "theme_id": "主题ID",
      "conflict_type": "content_conflict|tag_mismatch|reinforcement|obsolete",
      "reason": "详细解释冲突原因",
      "suggested_summary": "建议的主题新摘要（如果需要修改）",
      "suggested_tag": "建议的新标签（如果需要修改）"
    }}
  ]
}}

注意：
1. 只返回真正存在的冲突
2. reinforcement类型也视为一种"正向冲突"，表示主题得到强化
3. 如果没有冲突，返回空数组
4. 必须返回有效的JSON格式"""

EVOLUTION_SUGGESTION_SYSTEM_PROMPT = """你是主题演进分析专家。你的任务是分析主题及其相关笔记，提出主题演进建议。

演进分析原则：
1. 主题是否准确概括了所有相关笔记的内容？
2. 主题标签是否仍然合适？
3. 是否需要调整主题表述以更好地反映笔记集合？
4. 是否存在子主题或需要拆分的情况？

演进建议类型：
- summary_update：建议更新主题摘要
- tag_update：建议调整主题标签
- no_change：主题状态良好，无需调整
- split_suggestion：建议拆分为多个子主题

输出必须是JSON格式。"""

EVOLUTION_SUGGESTION_USER_TEMPLATE = """请分析以下主题的演进需求：

主题信息：
- ID：{theme_id}
- 当前摘要：{theme_summary}
- 当前标签：{theme_tag}
- 关联笔记数：{node_count}

相关笔记：
{nodes_info}

请按以下JSON格式返回演进建议：

{{
  "suggestions": [
    {{
      "conflict_type": "content_conflict|tag_mismatch|reinforcement|obsolete",
      "reason": "详细说明建议原因",
      "suggested_summary": "建议的新摘要（如果有）",
      "suggested_tag": "建议的新标签（如果有）"
    }}
  ]
}}

注意：
1. 基于笔记集合的整体内容提出合理建议
2. 如果主题状态良好，可以返回空数组或仅reinforcement类型
3. 必须返回有效的JSON格式"""


class ThemeEvolutionAnalyzer:
    """Analyzes themes for conflicts and generates evolution suggestions."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        theme_store=None
    ) -> None:
        """Initialize the evolution analyzer.

        Args:
            api_key: MiniMax API key (defaults to settings)
            base_url: MiniMax API base URL (defaults to settings)
            model: Model name (defaults to settings)
            theme_store: Optional ThemeStore instance for persistence
        """
        self.api_key = api_key or settings.minimax_api_key
        self.base_url = base_url or settings.minimax_base_url
        self.model = model or settings.minimax_model
        self.theme_store = theme_store

        if not self.api_key:
            raise ValueError("MiniMax API key is required for theme evolution analysis.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _call_api(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call MiniMax API with retry logic."""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        openai_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            openai_messages.append({"role": role, "content": content})

        payload = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": 0.3,
            "max_tokens": 2000
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _parse_json_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse API response and extract JSON data."""
        try:
            base_resp = response.get("base_resp", {})
            if base_resp.get("status_code", 0) != 0:
                raise ValueError(f"MiniMax API error: {base_resp.get('status_msg', 'Unknown error')}")

            content = response.get("reply", "")

            if not content:
                choices = response.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")

            if not content:
                raise ValueError("Empty content in API response")

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

    async def detect_conflicts(
        self,
        new_node: Node,
        all_themes: list[Theme]
    ) -> list[ThemeEvolutionSuggestion]:
        """Detect conflicts between a new node and existing themes.

        Args:
            new_node: The new node to analyze
            all_themes: List of all existing themes to check against

        Returns:
            List of conflict suggestions
        """
        if not all_themes:
            return []

        # Build themes info for prompt
        themes_info = []
        for theme in all_themes[:10]:  # Limit to 10 themes for context
            themes_info.append(
                f"- 主题ID: {theme.id}\n"
                f"  摘要: {theme.summary}\n"
                f"  标签: {theme.tag}\n"
                f"  笔记数: {len(theme.node_ids)}"
            )

        user_prompt = CONFLICT_DETECTION_USER_TEMPLATE.format(
            node_proposition=new_node.processed.proposition,
            node_raw_input=new_node.raw_input[:500],
            node_tags=", ".join(new_node.tags),
            themes_info="\n\n".join(themes_info)
        )

        messages = [
            {"role": "system", "content": CONFLICT_DETECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = await self._call_api(messages)
            data = self._parse_json_response(response)

            suggestions = []
            for conflict in data.get("conflicts", []):
                try:
                    conflict_type = ConflictType(conflict.get("conflict_type", "content_conflict"))
                except ValueError:
                    conflict_type = ConflictType.CONTENT_CONFLICT

                suggestion = ThemeEvolutionSuggestion(
                    theme_id=conflict.get("theme_id", ""),
                    suggested_summary=conflict.get("suggested_summary"),
                    suggested_tag=conflict.get("suggested_tag"),
                    conflict_type=conflict_type,
                    reason=conflict.get("reason", "检测到冲突"),
                    affected_node_ids=[new_node.id]
                )
                suggestions.append(suggestion)

            return suggestions

        except Exception as e:
            print(f"Conflict detection failed: {e}")
            return []

    async def generate_evolution_suggestions(
        self,
        theme: Theme,
        related_nodes: list[Node]
    ) -> list[ThemeEvolutionSuggestion]:
        """Generate evolution suggestions for a theme based on its related nodes.

        Args:
            theme: The theme to analyze
            related_nodes: List of nodes belonging to this theme

        Returns:
            List of evolution suggestions
        """
        if not related_nodes:
            return []

        # Build nodes info for prompt
        nodes_info = []
        for node in related_nodes[:5]:  # Limit to 5 nodes for context
            nodes_info.append(
                f"- 笔记ID: {node.id}\n"
                f"  标题: {node.processed.proposition}\n"
                f"  标签: {', '.join(node.tags)}"
            )

        user_prompt = EVOLUTION_SUGGESTION_USER_TEMPLATE.format(
            theme_id=theme.id,
            theme_summary=theme.summary,
            theme_tag=theme.tag,
            node_count=len(related_nodes),
            nodes_info="\n\n".join(nodes_info)
        )

        messages = [
            {"role": "system", "content": EVOLUTION_SUGGESTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = await self._call_api(messages)
            data = self._parse_json_response(response)

            suggestions = []
            for sugg in data.get("suggestions", []):
                try:
                    conflict_type = ConflictType(sugg.get("conflict_type", "reinforcement"))
                except ValueError:
                    conflict_type = ConflictType.REINFORCEMENT

                suggestion = ThemeEvolutionSuggestion(
                    theme_id=theme.id,
                    suggested_summary=sugg.get("suggested_summary"),
                    suggested_tag=sugg.get("suggested_tag"),
                    conflict_type=conflict_type,
                    reason=sugg.get("reason", "演进分析建议"),
                    affected_node_ids=[n.id for n in related_nodes]
                )
                suggestions.append(suggestion)

            return suggestions

        except Exception as e:
            print(f"Evolution suggestion generation failed: {e}")
            return []

    async def apply_evolution(self, suggestion_id: str) -> bool:
        """Apply an evolution suggestion to its target theme.

        Args:
            suggestion_id: ID of the suggestion to apply

        Returns:
            True if successfully applied
        """
        from rhizome.core.evolution_store import EvolutionStore

        store = EvolutionStore()
        suggestion = store.get_suggestion(suggestion_id)

        if not suggestion:
            print(f"Suggestion {suggestion_id} not found")
            return False

        if suggestion.status != SuggestionStatus.PENDING:
            print(f"Suggestion {suggestion_id} is not pending (status: {suggestion.status})")
            return False

        if not self.theme_store:
            print("Theme store not available")
            return False

        theme = self.theme_store.get_theme(suggestion.theme_id)
        if not theme:
            print(f"Theme {suggestion.theme_id} not found")
            return False

        try:
            # Record current version before changes
            previous_version = theme.version
            theme.record_version(reason=f"Applying evolution suggestion: {suggestion.reason}")

            # Apply changes if suggested
            if suggestion.suggested_summary:
                theme.summary = suggestion.suggested_summary
            if suggestion.suggested_tag:
                theme.tag = suggestion.suggested_tag

            # Update evolution status based on conflict type
            if suggestion.conflict_type == ConflictType.OBSOLETE:
                theme.evolution_status = "deprecated"
            elif suggestion.conflict_type == ConflictType.CONTENT_CONFLICT:
                theme.evolution_status = "evolving"
            else:
                theme.evolution_status = "stable"

            # Save theme
            self.theme_store.save_theme(theme)

            # Update suggestion status
            suggestion.status = SuggestionStatus.APPLIED
            suggestion.applied_at = datetime.now()
            suggestion.previous_version = previous_version
            store.save_suggestion(suggestion)

            return True

        except Exception as e:
            print(f"Failed to apply evolution: {e}")
            return False

    async def rollback_evolution(self, theme_id: str, version: int) -> bool:
        """Rollback a theme to a specific version.

        Args:
            theme_id: ID of the theme to rollback
            version: Target version number to rollback to

        Returns:
            True if successfully rolled back
        """
        if not self.theme_store:
            print("Theme store not available")
            return False

        theme = self.theme_store.get_theme(theme_id)
        if not theme:
            print(f"Theme {theme_id} not found")
            return False

        # Find the target version in evolution history
        target_version = None
        for v in theme.evolution_history:
            if v.version == version:
                target_version = v
                break

        if not target_version:
            print(f"Version {version} not found in theme history")
            return False

        try:
            # Record current state before rollback
            theme.record_version(reason=f"Rollback to version {version}")

            # Restore to target version
            theme.summary = target_version.summary
            theme.tag = target_version.tag
            theme.evolution_status = "stable"

            # Save theme
            self.theme_store.save_theme(theme)

            # Update any applied suggestions for this theme to rolled_back status
            from rhizome.core.evolution_store import EvolutionStore
            store = EvolutionStore()
            suggestions = store.get_suggestions_for_theme(theme_id)

            for sugg in suggestions:
                if sugg.status == SuggestionStatus.APPLIED and sugg.previous_version == version:
                    sugg.status = SuggestionStatus.ROLLED_BACK
                    store.save_suggestion(sugg)

            return True

        except Exception as e:
            print(f"Failed to rollback evolution: {e}")
            return False


class MockThemeEvolutionAnalyzer(ThemeEvolutionAnalyzer):
    """Mock evolution analyzer for testing without API calls."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize mock analyzer without API key check."""
        self.api_key = "mock"
        self.base_url = "mock"
        self.model = "mock"
        self.theme_store = kwargs.get("theme_store")

    async def detect_conflicts(
        self,
        new_node: Node,
        all_themes: list[Theme]
    ) -> list[ThemeEvolutionSuggestion]:
        """Return mock conflict detections."""
        suggestions = []

        for theme in all_themes[:2]:  # Generate suggestions for first 2 themes
            # Simple heuristic: if tags don't match, suggest tag update
            if new_node.tags and theme.tag not in new_node.tags:
                suggestions.append(ThemeEvolutionSuggestion(
                    theme_id=theme.id,
                    suggested_tag=new_node.tags[0],
                    conflict_type=ConflictType.TAG_MISMATCH,
                    reason=f"新笔记标签({', '.join(new_node.tags)})与主题标签({theme.tag})不一致",
                    affected_node_ids=[new_node.id]
                ))
            else:
                # Otherwise suggest reinforcement
                suggestions.append(ThemeEvolutionSuggestion(
                    theme_id=theme.id,
                    conflict_type=ConflictType.REINFORCEMENT,
                    reason="新笔记与主题内容一致，建议保持当前状态",
                    affected_node_ids=[new_node.id]
                ))

        return suggestions

    async def generate_evolution_suggestions(
        self,
        theme: Theme,
        related_nodes: list[Node]
    ) -> list[ThemeEvolutionSuggestion]:
        """Return mock evolution suggestions."""
        if len(related_nodes) > 3:
            return [ThemeEvolutionSuggestion(
                theme_id=theme.id,
                suggested_summary=f"[演进建议] {theme.summary}",
                conflict_type=ConflictType.REINFORCEMENT,
                reason=f"主题包含{len(related_nodes)}条笔记，建议完善描述",
                affected_node_ids=[n.id for n in related_nodes]
            )]
        return []

    async def apply_evolution(self, suggestion_id: str) -> bool:
        """Mock apply - always returns True."""
        return True

    async def rollback_evolution(self, theme_id: str, version: int) -> bool:
        """Mock rollback - always returns True."""
        return True
