"""Tests for LLM processor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from rhizome.core.models import Node, Processed, Source
from rhizome.core.llm_processor import LLMProcessor, MockLLMProcessor


class TestMockLLMProcessor:
    """Tests for MockLLMProcessor."""

    @pytest.fixture
    def processor(self):
        """Create a mock processor."""
        return MockLLMProcessor()

    @pytest.mark.asyncio
    async def test_process_returns_processed_object(self, processor):
        """Test process() returns correct Processed object."""
        raw_input = "This is a test input about machine learning."

        processed, tags, potential_links, refined_content = await processor.process(raw_input)

        assert isinstance(processed, Processed)
        assert isinstance(refined_content, str)
        assert len(processed.open_questions) > 0

    @pytest.mark.asyncio
    async def test_process_tags(self, processor):
        """Test process() returns expected tags."""
        raw_input = "Test input"

        processed, tags, potential_links, refined_content = await processor.process(raw_input)

        assert isinstance(tags, list)
        assert "vague" in tags
        assert "needs_thinking" in tags

    @pytest.mark.asyncio
    async def test_process_with_existing_nodes(self, processor):
        """Test process() with existing_nodes generates potential_links."""
        existing_node = Node(
            raw_input="existing",
            processed=Processed(proposition="Existing node proposition about AI")
        )

        processed, tags, potential_links, refined_content = await processor.process(
            "Test input",
            existing_nodes=[existing_node]
        )

        assert len(potential_links) > 0
        assert "target_node_summary" in potential_links[0]
        assert "relation_type" in potential_links[0]
        assert "reasoning" in potential_links[0]

    @pytest.mark.asyncio
    async def test_process_potential_links_format(self, processor):
        """Test potential_links structure."""
        existing_nodes = [
            Node(raw_input="test1", processed=Processed(proposition="Proposition 1")),
            Node(raw_input="test2", processed=Processed(proposition="Proposition 2")),
        ]

        processed, tags, potential_links, refined_content = await processor.process(
            "Test input",
            existing_nodes=existing_nodes
        )

        # Mock processor limits to 2 potential links
        assert len(potential_links) <= 2
        for link in potential_links:
            assert "target_node_summary" in link
            assert "relation_type" in link
            assert "reasoning" in link

    @pytest.mark.asyncio
    async def test_health_check(self, processor):
        """Test health_check() returns True for mock."""
        result = await processor.health_check()

        assert result is True

    def test_initialization_no_api_key_required(self):
        """Test MockLLMProcessor doesn't require API key."""
        processor = MockLLMProcessor()

        assert processor.api_key == "mock"
        assert processor.base_url == "mock"
        assert processor.model == "mock"


class TestLLMProcessorValidation:
    """Tests for LLMProcessor validation logic."""

    def test_initialization_requires_api_key(self):
        """Test LLMProcessor raises error without API key."""
        with patch("rhizome.core.llm_client.settings") as mock_settings:
            mock_settings.minimax_api_key = None
            mock_settings.minimax_base_url = "http://test"
            mock_settings.minimax_model = "test-model"

            with pytest.raises(ValueError, match="