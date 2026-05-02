"""LLM processing module for Rhizome Thinking."""

import json
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rhizome.config import settings
from rhizome.core.models import Node, Processed, Source, TagType


SYSTEM_PROMPT = """你是一个个人知识库的智能助手。你的任务是将用户的输入整理成结构化的知识节点。

核心原则：
1. 保留原始输入，不做过度修改
2. 标题应该极其简洁，用5-10个字概括核心内容（像文章标题一样简短有力）
3. 从用户输入中识别并提取用户明确提出的开放问题/困惑
4. 分配准确的内容性质标签
5. 生成精炼内容：将原始输入重组为结构化、易读的版本，保留原意但提升可读性

标题生成规则（非常重要）：
1. 标题必须简短精炼，控制在5-10个字，像新闻标题或文章标题一样
2. 示例好标题："记忆的本质"、"AI意识探讨"、"注意力机制"、"权重系统设计"
3. 避免冗长描述，不要加"关于"、"论"等前缀，直接给出核心概念
4. 如果涉及多个概念，用"XX与YY"形式，如"记忆与注意力"
5. 技术内容用专业术语，如"Transformer架构"、"在线学习机制"
6. 标题要能让人一眼就知道主题，但不要过长

精炼内容（refined_content）生成规则：
1. 基于原始输入，重组为结构清晰、逻辑连贯的文本
2. 保留原始含义和关键信息，不做过度解读或扩展
3. 改进可读性：使用适当的段落划分、列表、强调等格式
4. 去除冗余表达，使语言更简洁流畅
5. 如果原始输入已经是简洁清晰的，可以适度优化表达
6. 长度应与原始输入相当，不要过度扩展

内容性质标签定义：
- definitive: 有依据的明确结论或陈述。用户有明确的支持依据，表达清晰。
- inferred: 基于已有内容推断出的结论。有一定逻辑支撑，但不够确定。
- vague: 模糊感知，尚未能清晰表达。用户自己也说不清楚，只是隐约觉得有关联。
- needs_thinking: 明确需要进一步思考的问题。以疑问句形式提出，需要后续探索。
- cross-domain: 跨越多个主题领域的想法。连接了不同学科或领域的概念。

关系类型定义：
- support: 支持/证实。一个节点的内容支持另一个节点的观点。
- contradict: 矛盾/反驳。一个节点的内容与另一个节点相矛盾。
- extend: 延伸/发展。一个节点是另一个节点的延伸或发展。
- source: 来源/基础。一个节点是另一个节点的信息来源。
- analogy: 类比/相似。两个节点之间存在类比或相似关系。

输入确定性判断规则：
1. 明确断言 → 使用 definitive 标签，标题概括核心结论
2. 模糊联想 → 使用 vague 标签，标题描述探索方向
3. 问题记录 → 使用 needs_thinking 标签，标题概括问题主题
4. 纯粹碎片 → 保留核心意象，使用 vague 标签，注明"待发展"

重要：
1. 标题必须让人一看就懂，不要为了追求简洁而失去清晰度
2. 你必须从用户的原始输入中识别并提取用户提出的问题，而不是生成新的问题
3. 如果输入涉及多个领域，cross-domain标签是必须的
4. 精炼内容应忠实于原始输入，改善结构而非改变含义"""

USER_PROMPT_TEMPLATE = """请处理以下输入，生成知识节点：

<raw_input>
{raw_input}
</raw_input>

来源信息：
- 类型: {source_type}
- 标题: {source_title}
- 位置: {source_location}

请根据输入的确定性，按照以下 JSON 格式返回：

{{
  "title": "5-10字的简短标题，像新闻标题一样精炼，如'记忆的本质'、'AI意识探讨'",
  "questions": ["从用户输入中识别出的问题/困惑，如果用户没有提出任何问题则返回空数组。注意：这是用户的问题，不是AI生成的问题"],
  "tags": ["definitive", "inferred", "vague", "needs_thinking", "cross-domain" 中的一个或多个],
  "refined_content": "精炼后的内容：结构清晰、逻辑连贯的版本，保留原意但提升可读性。使用适当的段落和格式组织内容",
  "potential_links": [
    {{
      "target_node_summary": "可能相关的已有节点摘要（仅描述，不需要ID）",
      "relation_type": "support|contradict|extend|source|analogy",
      "reasoning": "为什么认为它们相关"
    }}
  ]
}}

注意：
1. title 必须简短有力，5-10个字，像文章标题一样。例如："记忆的本质"、"注意力机制"、"权重系统设计"
2. 不要加"关于"、"论"、"探讨"等前缀，直接给出核心概念名称
3. questions 必须来自用户原始输入中明确提出的问题，不要自己生成问题
4. tags 是多选的，可以分配多个标签。如果输入涉及多个领域，必须包含cross-domain
5. refined_content 是对原始输入的结构化重组，改善可读性但不改变原意
6. potential_links 是基于内容相似性的推测，用于给用户参考
"""


class LLMProcessor:
    """Processes raw input using MiniMax API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> None:
        """Initialize the LLM processor.

        Args:
            api_key: MiniMax API key (defaults to settings)
            base_url: MiniMax API base URL (defaults to settings)
            model: Model name (defaults to settings)
        """
        self.api_key = api_key or settings.minimax_api_key
        self.base_url = base_url or settings.minimax_base_url
        self.model = model or settings.minimax_model

        if not self.api_key:
            raise ValueError("MiniMax API key is required. Set MINIMAX_API_KEY environment variable.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _call_api(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call MiniMax API with retry logic.

        Args:
            messages: List of message dictionaries with 'role' and 'content'

        Returns:
            API response
        """
        # Use OpenAI-compatible endpoint
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Use standard OpenAI message format
        openai_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                openai_messages.append({"role": "system", "content": content})
            elif role == "user":
                openai_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                openai_messages.append({"role": "assistant", "content": content})

        # OpenAI-compatible payload
        payload = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": 0.3,
            "max_tokens": 4000
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if not response.is_success:
                raise httpx.HTTPStatusError(
                    f"MiniMax API returned {response.status_code}: {response.text[:500]}",
                    request=response.request,
                    response=response
                )
            return response.json()

    def _parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse API response and extract structured data.

        Args:
            response: API response

        Returns:
            Parsed data
        """
        try:
            # Check for MiniMax error response
            base_resp = response.get("base_resp", {})
            if base_resp.get("status_code", 0) != 0:
                raise ValueError(f"MiniMax API error: {base_resp.get('status_msg', 'Unknown error')}")

            # MiniMax uses 'reply' field for the response content
            content = response.get("reply", "")

            # Fallback to OpenAI format if reply is empty
            if not content:
                choices = response.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")

            if not content:
                raise ValueError("Empty content in API response")

            # Try to find JSON in the content
            # The model might wrap JSON in markdown code blocks
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            data = json.loads(json_str)

            # Validate required fields (support both old and new field names)
            if "title" not in data and "proposition" not in data:
                raise ValueError("Missing 'title' or 'proposition' field in response")

            # Normalize field names (support both old and new formats)
            if "title" not in data and "proposition" in data:
                data["title"] = data["proposition"]
            if "questions" not in data and "open_questions" in data:
                data["questions"] = data["open_questions"]

            # Set defaults
            data.setdefault("questions", [])
            data.setdefault("tags", ["vague"])
            data.setdefault("potential_links", [])
            data.setdefault("refined_content", "")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from API response: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse API response: {e}")

    async def process(
        self,
        raw_input: str,
        source: Optional[Source] = None,
        existing_nodes: Optional[list[Node]] = None
    ) -> tuple[Processed, list[TagType], list[dict], str]:
        """Process raw input and return structured data.

        Args:
            raw_input: The raw user input
            source: Source information
            existing_nodes: List of existing nodes for link suggestions

        Returns:
            Tuple of (Processed, tags, potential_links, refined_content)
        """
        source = source or Source(type="original")

        # Build context from existing nodes if provided
        context = ""
        if existing_nodes:
            context = "\n\n已有节点参考（用于判断潜在连接）：\n"
            for node in existing_nodes[:10]:  # Limit to 10 for context window
                context += f"- {node.processed.proposition[:500]}\n"

        # Build user prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            raw_input=raw_input,
            source_type=source.type,
            source_title=source.title or "未指定",
            source_location=source.location or "未指定"
        ) + context

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        # Call API
        response = await self._call_api(messages)

        # Parse response
        data = self._parse_response(response)

        # Create Processed object (use title as proposition for backward compatibility)
        processed = Processed(
            proposition=data["title"],
            open_questions=data["questions"],
            refined_content=data["refined_content"]
        )

        # Validate tags
        valid_tags = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]
        tags = [t for t in data["tags"] if t in valid_tags]
        if not tags:
            tags = ["vague"]

        return processed, tags, data["potential_links"], data["refined_content"]

    async def health_check(self) -> bool:
        """Check if the API is accessible.

        Returns:
            True if API is accessible
        """
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' and nothing else."}
            ]
            response = await self._call_api(messages)
            return True
        except Exception:
            return False

    async def regenerate_refined_content(self, node: Node) -> str:
        """Regenerate refined content for an existing node.

        Args:
            node: The node to regenerate refined content for

        Returns:
            New refined content string
        """
        REFINE_PROMPT = """你是一个内容精炼专家。请基于以下节点的原始输入和核心命题，重新生成结构化、易读的精炼内容。

核心命题（标题）：
{proposition}

原始输入：
{raw_input}

标签：{tags}

请生成精炼内容（refined_content）：
1. 基于原始输入，重组为结构清晰、逻辑连贯的文本
2. 保留原始含义和关键信息，不做过度解读或扩展
3. 改进可读性：使用适当的段落划分、列表、强调等格式
4. 去除冗余表达，使语言更简洁流畅
5. 长度应与原始输入相当，不要过度扩展

直接返回精炼后的内容文本，不需要JSON格式或其他包装。"""

        user_prompt = REFINE_PROMPT.format(
            proposition=node.processed.proposition,
            raw_input=node.raw_input,
            tags=", ".join(node.tags)
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        response = await self._call_api(messages)

        # Extract content from response
        content = response.get("reply", "")
        if not content:
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")

        content = content.strip() if content else ""

        # Remove <think>...</think> blocks
        import re
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        return content


class MockLLMProcessor(LLMProcessor):
    """Mock processor for testing without API calls."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> None:
        """Initialize mock processor with mock API values."""
        super().__init__(api_key="mock", base_url="mock", model="mock")

    def _generate_mock_title(self, raw_input: str) -> str:
        """Generate a mock short title (5-10 chars) based on content."""
        # Extract key concepts from the text
        keywords = []
        if "人工智能" in raw_input or "AI" in raw_input:
            keywords.append("AI")
        if "思考" in raw_input or "认知" in raw_input:
            keywords.append("思考")
        if "记忆" in raw_input:
            keywords.append("记忆")
        if "学习" in raw_input:
            keywords.append("学习")
        if "系统" in raw_input:
            keywords.append("系统")
        if "模型" in raw_input:
            keywords.append("模型")
        if "设计" in raw_input:
            keywords.append("设计")
        if "问题" in raw_input or "疑问" in raw_input:
            keywords.append("疑问")
        if "未来" in raw_input:
            keywords.append("未来")
            
        if keywords:
            # Combine up to 2 keywords
            if len(keywords) >= 2:
                return f"{keywords[0]}与{keywords[1]}"
            else:
                return keywords[0]
        else:
            # Default titles based on length
            return "知识笔记"

    def _generate_mock_refined_content(self, raw_input: str) -> str:
        """Generate truly structured refined content with sections and organization."""
        # Split raw input into sentences for processing
        sentences = raw_input.replace('。', '|').replace('，', '|').replace('\n', '|').split('|')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Identify main themes
        has_ai = "人工智能" in raw_input or "AI" in raw_input
        has_thinking = "思考" in raw_input or "认知" in raw_input
        has_challenge = "问题" in raw_input or "挑战" in raw_input or "风险" in raw_input
        has_future = "未来" in raw_input or "发展" in raw_input
        
        sections = []
        
        # Section 1: Core content summary
        if sentences:
            sections.append("## 核心观点\n")
            # Take first 1-2 meaningful sentences
            core_content = sentences[0]
            if len(sentences) > 1 and len(core_content) < 30:
                core_content += "，" + sentences[1]
            sections.append(core_content + "\n")
        
        # Section 2: Key points
        if len(sentences) >= 3:
            sections.append("\n## 关键要点\n")
            for i, sentence in enumerate(sentences[2:5], 1):
                if sentence and len(sentence) > 5:
                    sections.append(f"{i}. {sentence}\n")
        
        # Section 3: Reflections/Challenges
        if has_challenge or has_future:
            sections.append("\n## 待探索问题\n")
            if has_challenge:
                sections.append("- 如何应对相关挑战与风险\n")
            if has_future:
                sections.append("- 未来的发展方向与可能性\n")
            sections.append("- 需要进一步深入思考的议题\n")
        
        # Section 4: Conclusion
        sections.append("\n## 总结\n")
        if sentences:
            last_sentence = sentences[-1] if len(sentences[-1]) > 10 else sentences[-2] if len(sentences) > 1 else sentences[0]
            sections.append(f"{last_sentence}")
        
        refined = "".join(sections)
        return refined

    async def process(
        self,
        raw_input: str,
        source: Optional[Source] = None,
        existing_nodes: Optional[list[Node]] = None
    ) -> tuple[Processed, list[TagType], list[dict], str]:
        """Return mock processed data with properly structured refined content."""
        # Generate proper short title (5-10 chars)
        title = self._generate_mock_title(raw_input)
        
        # Generate structured refined content
        refined_content = self._generate_mock_refined_content(raw_input)
        
        processed = Processed(
            proposition=title,
            open_questions=["这是一个需要进一步思考的问题"],
            refined_content=refined_content
        )
        tags = ["vague", "needs_thinking"]
        potential_links = []

        if existing_nodes:
            potential_links = [
                {
                    "target_node_summary": node.processed.proposition[:50],
                    "relation_type": "analogy",
                    "reasoning": "基于内容的相似性判断"
                }
                for node in existing_nodes[:2]
            ]

        return processed, tags, potential_links, refined_content

    async def health_check(self) -> bool:
        """Always return True for mock."""
        return True

    async def regenerate_refined_content(self, node: Node) -> str:
        """Return properly structured mock refined content."""
        return self._generate_mock_refined_content(node.raw_input)
