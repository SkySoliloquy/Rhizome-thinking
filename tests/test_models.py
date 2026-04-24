"""Tests for data models."""

import pytest
from datetime import datetime

from rhizome.core.models import Link, Node, Processed, Source


class TestSource:
    def test_source_creation(self):
        source = Source(type="book", title="Test Book", location="Chapter 1")
        assert source.type == "book"
        assert source.title == "Test Book"
        assert source.location == "Chapter 1"
    
    def test_source_defaults(self):
        source = Source()
        assert source.type == "original"
        assert source.title is None
        assert source.location is None
    
    def test_source_str(self):
        source = Source(type="paper", title="Test Paper")
        assert "paper" in str(source)
        assert "Test Paper" in str(source)


class TestProcessed:
    def test_processed_creation(self):
        processed = Processed(
            proposition="Test proposition",
            open_questions=["Question 1?", "Question 2?"]
        )
        assert processed.proposition == "Test proposition"
        assert len(processed.open_questions) == 2
    
    def test_processed_defaults(self):
        processed = Processed(proposition="Test")
        assert processed.open_questions == []


class TestLink:
    def test_link_creation(self):
        link = Link(
            target_id="123e4567-e89b-12d3-a456-426614174000",
            relation_type="support",
            strength=0.8,
            confirmed=True
        )
        assert link.target_id == "123e4567-e89b-12d3-a456-426614174000"
        assert link.relation_type == "support"
        assert link.strength == 0.8
        assert link.confirmed is True
    
    def test_link_defaults(self):
        link = Link(target_id="test-id", relation_type="analogy")
        assert link.strength == 0.5
        assert link.confirmed is False


class TestNode:
    def test_node_creation(self):
        node = Node(
            raw_input="Test input",
            processed=Processed(proposition="Test proposition"),
            tags=["definitive"]
        )
        assert node.raw_input == "Test input"
        assert node.processed.proposition == "Test proposition"
        assert "definitive" in node.tags
        assert len(node.id) == 36  # UUID length
    
    def test_node_to_markdown(self):
        node = Node(
            raw_input="This is the raw input",
            processed=Processed(
                proposition="This is the proposition",
                open_questions=["What if?"]
            ),
            tags=["definitive", "cross-domain"],
            source=Source(type="paper", title="Test Paper")
        )
        
        markdown = node.to_markdown()
        
        # Check frontmatter
        assert "---" in markdown
        assert f'id: "{node.id}"' in markdown
        assert 'type: "paper"' in markdown
        assert 'title: "Test Paper"' in markdown
        assert "definitive" in markdown
        assert "cross-domain" in markdown
        
        # Check content sections
        assert "## 核心命题" in markdown
        assert "This is the proposition" in markdown
        assert "## 开放问题" in markdown
        assert "What if?" in markdown
        assert "## 原始输入" in markdown
        assert "This is the raw input" in markdown
    
    def test_node_from_markdown(self):
        markdown = '''---
id: "test-id-123"
timestamp: "2026-04-20T10:30:00"
source:
  type: "book"
  title: "Test Book"
tags:
  - "definitive"
  - "cross-domain"
links:
  - target_id: "target-456"
    relation_type: "support"
    strength: 0.8
    confirmed: true
---

# Test Proposition

## 核心命题

This is the core proposition.

## 开放问题

1. First question?
2. Second question?

---

## 原始输入

This is the original raw input text.
'''
        
        node = Node.from_markdown(markdown)
        
        assert node.id == "test-id-123"
        assert node.source.type == "book"
        assert node.source.title == "Test Book"
        assert "definitive" in node.tags
        assert node.processed.proposition == "This is the core proposition."
        assert len(node.processed.open_questions) == 2
        assert node.raw_input == "This is the original raw input text."
        assert len(node.links) == 1
        assert node.links[0].target_id == "target-456"
    
    def test_node_roundtrip(self):
        """Test that a node can be converted to markdown and back."""
        original = Node(
            raw_input="Original input",
            processed=Processed(
                proposition="Core proposition",
                open_questions=["Q1?", "Q2?"]
            ),
            tags=["inferred"],
            source=Source(type="article", title="Test Article", location="Section 2")
        )
        
        markdown = original.to_markdown()
        restored = Node.from_markdown(markdown)
        
        assert restored.raw_input == original.raw_input
        assert restored.processed.proposition == original.processed.proposition
        assert restored.processed.open_questions == original.processed.open_questions
        assert restored.tags == original.tags
        assert restored.source.type == original.source.type
        assert restored.source.title == original.source.title
