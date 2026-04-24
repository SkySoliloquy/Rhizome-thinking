"""Data models for Rhizome Thinking."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_serializer


TagType = Literal["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]
RelationType = Literal["support", "contradict", "extend", "source", "analogy"]
SourceType = Literal["book", "paper", "article", "original"]


class Source(BaseModel):
    """Source information for a node."""
    
    type: SourceType = Field(
        default="original",
        description="Type of the source"
    )
    title: Optional[str] = Field(
        default=None,
        description="Title of the source"
    )
    location: Optional[str] = Field(
        default=None,
        description="Specific location in the source (chapter, page, etc.)"
    )
    
    def __str__(self) -> str:
        parts = [self.type]
        if self.title:
            parts.append(f'"{self.title}"')
        if self.location:
            parts.append(f"at {self.location}")
        return " ".join(parts)


class Processed(BaseModel):
    """LLM-processed content for a node."""
    
    proposition: str = Field(
        ...,
        description="Core proposition distilled from raw input",
        min_length=1
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Open questions left by this idea"
    )
    
    def __str__(self) -> str:
        result = f"Proposition: {self.proposition}"
        if self.open_questions:
            result += f"\nOpen Questions: {len(self.open_questions)}"
        return result


class Link(BaseModel):
    """Connection between nodes."""
    
    target_id: str = Field(
        ...,
        description="ID of the target node"
    )
    relation_type: RelationType = Field(
        ...,
        description="Type of relationship"
    )
    strength: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Connection strength assessed by LLM (0.0 - 1.0)"
    )
    confirmed: bool = Field(
        default=False,
        description="Whether the connection is confirmed by user"
    )
    auto_confirmed: bool = Field(
        default=False,
        description="Whether the connection was auto-confirmed"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reasoning for why this connection exists"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this link was created"
    )
    
    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()
    
    def __str__(self) -> str:
        status = "✓" if self.confirmed else "?"
        return f"[{status}] {self.relation_type} -> {self.target_id} ({self.strength:.2f})"


class Node(BaseModel):
    """Core data unit in the knowledge base."""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Creation time"
    )
    source: Source = Field(
        default_factory=Source,
        description="Source information"
    )
    raw_input: str = Field(
        ...,
        description="Original input text, never modified",
        min_length=1
    )
    processed: Processed = Field(
        ...,
        description="LLM-processed structured content"
    )
    tags: list[TagType] = Field(
        default_factory=list,
        description="Content nature tags"
    )
    links: list[Link] = Field(
        default_factory=list,
        description="Connections to other nodes"
    )
    embedding: Optional[list[float]] = Field(
        default=None,
        description="Vector representation for semantic retrieval (Stage 2)"
    )
    
    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()
    
    def to_markdown(self) -> str:
        """Convert node to markdown format."""
        lines = [
            "---",
            f'id: "{self.id}"',
            f'timestamp: "{self.timestamp.isoformat()}"',
            "source:",
            f'  type: "{self.source.type}"',
        ]
        
        if self.source.title:
            lines.append(f'  title: "{self.source.title}"')
        if self.source.location:
            lines.append(f'  location: "{self.source.location}"')
        
        lines.append("tags:")
        for tag in self.tags:
            lines.append(f'  - "{tag}"')
        
        if self.links:
            lines.append("links:")
            for link in self.links:
                lines.append(f'  - target_id: "{link.target_id}"')
                lines.append(f'    relation_type: "{link.relation_type}"')
                lines.append(f'    strength: {link.strength}')
                lines.append(f'    confirmed: {str(link.confirmed).lower()}')
                if link.reason:
                    lines.append(f'    reason: "{link.reason}"')
        
        lines.extend([
            "---",
            "",
            f"# {self.processed.proposition[:50]}{'...' if len(self.processed.proposition) > 50 else ''}",
            "",
            "## 标题",
            "",
            self.processed.proposition,
            "",
        ])
        
        if self.processed.open_questions:
            lines.extend([
                "## 问题",
                "",
            ])
            for i, question in enumerate(self.processed.open_questions, 1):
                lines.append(f"{i}. {question}")
            lines.append("")
        
        lines.extend([
            "---",
            "",
            "## 原始文件",
            "",
            self.raw_input,
            "",
        ])
        
        return "\n".join(lines)
    
    @classmethod
    def from_markdown(cls, content: str) -> "Node":
        """Parse node from markdown content."""
        import frontmatter
        
        post = frontmatter.loads(content)
        metadata = post.metadata
        
        # Parse source
        source_data = metadata.get("source", {})
        source = Source(**source_data) if isinstance(source_data, dict) else Source()
        
        # Parse links
        links_data = metadata.get("links", [])
        links = [Link(**link_data) for link_data in links_data]
        
        # Parse processed content from markdown body
        body = post.content
        proposition = ""
        open_questions = []
        raw_input = ""
        
        lines = body.split("\n")
        current_section = None
        section_content = []
        
        for line in lines:
            if line.startswith("# ") and not line.startswith("## "):
                continue  # Skip title
            elif line in ["## 标题", "## 核心命题"]:
                current_section = "proposition"
                section_content = []
            elif line in ["## 问题", "## 开放问题"]:
                if current_section == "proposition":
                    proposition = "\n".join(section_content).strip()
                current_section = "questions"
                section_content = []
            elif line in ["## 原始文件", "## 原始输入"]:
                if current_section == "questions":
                    # Parse questions
                    for q_line in section_content:
                        q_line = q_line.strip()
                        if q_line and q_line[0].isdigit():
                            # Remove numbering like "1. "
                            question = q_line.split(".", 1)[-1].strip()
                            if question:
                                open_questions.append(question)
                elif current_section == "proposition":
                    proposition = "\n".join(section_content).strip()
                current_section = "raw_input"
                section_content = []
            elif line == "---":
                continue
            elif current_section:
                section_content.append(line)
        
        if current_section == "raw_input":
            raw_input = "\n".join(section_content).strip()
        
        return cls(
            id=metadata.get("id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(metadata.get("timestamp", datetime.now().isoformat())),
            source=source,
            raw_input=raw_input,
            processed=Processed(
                proposition=proposition,
                open_questions=open_questions
            ),
            tags=metadata.get("tags", []),
            links=links
        )
    
    def get_summary(self) -> str:
        """Get a short summary of the node."""
        tags_str = ", ".join(self.tags) if self.tags else "no tags"
        links_str = f", {len(self.links)} links" if self.links else ""
        return f"[{self.id[:8]}] {self.processed.proposition[:60]}{'...' if len(self.processed.proposition) > 60 else ''} ({tags_str}{links_str})"
    
    def __str__(self) -> str:
        return self.get_summary()
