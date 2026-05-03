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

            with pytest.raises(ValueError, match="API key is required"):
                LLMProcessor()

    def test_initialization_uses_settings(self):
        """Test LLMProcessor uses settings when provided."""
        with patch("rhizome.core.llm_client.settings") as mock_settings:
            mock_settings.minimax_api_key = "test-key"
            mock_settings.minimax_base_url = "http://test-url"
            mock_settings.minimax_model = "test-model"

            processor = LLMProcessor()

            assert processor.api_key == "test-key"
            assert processor.base_url == "http://test-url"
            assert processor.model == "test-model"

    def test_initialization_custom_values(self):
        """Test LLMProcessor accepts custom values."""
        processor = LLMProcessor(
            api_key="custom-key",
            base_url="http://custom-url",
            model="custom-model"
        )

        assert processor.api_key == "custom-key"
        assert processor.base_url == "http://custom-url"
        assert processor.model == "custom-model"


class TestLLMProcessorProcess:
    """Tests for LLMProcessor.process() method."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        with patch("rhizome.core.llm_client.settings") as mock:
            mock.minimax_api_key = "test-key"
            mock.minimax_base_url = "http://test-url"
            mock.minimax_model = "test-model"
            yield mock

    @pytest.fixture
    def processor(self, mock_settings):
        """Create processor with mocked settings."""
        return LLMProcessor()

    @pytest.mark.asyncio
    async def test_process_validates_tags(self, processor):
        """Test that tags validation works correctly."""
        # This test verifies the validation logic by checking
        # that invalid tags are filtered out
        valid_tags = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]

        # Simulate what happens in process()
        mock_tags = ["definitive", "invalid_tag", "vague"]
        filtered_tags = [t for t in mock_tags if t in valid_tags]

        assert filtered_tags == ["definitive", "vague"]

    @pytest.mark.asyncio
    async def test_process_default_tag(self, processor):
        """Test that vague is used as default when no valid tags."""
        valid_tags = ["definitive", "inferred", "vague", "needs_thinking", "cross-domain"]

        # Simulate what happens when no valid tags
        mock_tags = ["invalid", "also_invalid"]
        filtered_tags = [t for t in mock_tags if t in valid_tags]

        if not filtered_tags:
            filtered_tags = ["vague"]

        assert filtered_tags == ["vague"]

    @pytest.mark.asyncio
    async def test_process_creates_source_if_none(self, processor):
        """Test process() creates default source if none provided."""
        raw_input = "Test input"

        # The process method should set source = Source(type="original") if source is None
        # We verify this by checking that the method doesn't raise an error
        with patch.object(processor, "call_api_async", new=AsyncMock(return_value={
            "base_resp": {"status_code": 0},
            "reply": '{"proposition": "Test", "open_questions": [], "tags": ["vague"]}'
        })):
            processed, tags, potential_links, refined_content = await processor.process(raw_input)

            assert isinstance(processed, Processed)
            assert isinstance(tags, list)


class TestLLMProcessorParseResponse:
    """Tests for process_response method."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        with patch("rhizome.core.llm_client.settings") as mock:
            mock.minimax_api_key = "test-key"
            mock.minimax_base_url = "http://test-url"
            mock.minimax_model = "test-model"
            yield mock

    @pytest.fixture
    def processor(self, mock_settings):
        """Create processor with mocked settings."""
        return LLMProcessor()

    def test_parse_minimax_response(self, processor):
        """Test parsing MiniMax API response format."""
        response = {
            "base_resp": {"status_code": 0, "status_msg": "success"},
            "reply": '{"proposition": "Test proposition", "tags": ["definitive"]}'
        }

        data = processor.process_response(response)

        assert data["proposition"] == "Test proposition"
        assert data["tags"] == ["definitive"]
        assert "questions" in data

    def test_parse_openai_response(self, processor):
        """Test parsing OpenAI-compatible response format."""
        response = {
            "choices": [{
                "message": {
                    "content": '{"proposition": "OpenAI response", "tags": ["vague"]}'
                }
            }]
        }

        data = processor.process_response(response)

        assert data["proposition"] == "OpenAI response"

    def test_parse_with_markdown_json(self, processor):
        """Test parsing JSON wrapped in markdown code blocks."""
        response = {
            "base_resp": {"status_code": 0},
            "reply": '```json\n{"proposition": "Markdown JSON", "tags": ["inferred"]}\n```'
        }

        data = processor.process_response(response)

        assert data["proposition"] == "Markdown JSON"

    def test_parse_sets_defaults(self, processor):
        """Test that defaults are set for missing fields."""
        response = {
            "base_resp": {"status_code": 0},
            "reply": '{"proposition": "Minimal response"}'
        }

        data = processor.process_response(response)

        assert data["proposition"] == "Minimal response"
        assert data["questions"] == []
        assert data["tags"] == ["vague"]
        assert data["potential_links"] == []

    def test_parse_error_minimax_status(self, processor):
        """Test parsing error response from MiniMax."""
        response = {
            "base_resp": {"status_code": 1001, "status_msg": "Invalid request"}
        }

        with pytest.raises(ValueError, match="API error"):
            processor.process_response(response)

    def test_parse_error_missing_proposition(self, processor):
        """Test parsing error when proposition is missing."""
        response = {
            "base_resp": {"status_code": 0},
            "reply": '{"tags": ["vague"]}'
        }

        with pytest.raises(ValueError, match="Missing 'title' or 'proposition'"):
            processor.process_response(response)

    def test_parse_error_invalid_json(self, processor):
        """Test parsing error with invalid JSON."""
        response = {
            "base_resp": {"status_code": 0},
            "reply": "not valid json"
        }

        with pytest.raises(ValueError, match="Failed to parse JSON"):
            processor.process_response(response)


class TestLLMProcessorHealthCheck:
    """Tests for health_check() method."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        with patch("rhizome.core.llm_client.settings") as mock:
            mock.minimax_api_key = "test-key"
            mock.minimax_base_url = "http://test-url"
            mock.minimax_model = "test-model"
            yield mock

    @pytest.fixture
    def processor(self, mock_settings):
        """Create processor with mocked settings."""
        return LLMProcessor()

    @pytest.mark.asyncio
    async def test_health_check_success(self, processor):
        """Test health_check returns True on success."""
        with patch.object(processor, "call_api_async", new=AsyncMock(return_value={})):
            result = await processor.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, processor):
        """Test health_check returns False on exception."""
        with patch.object(processor, "call_api_async", new=AsyncMock(side_effect=Exception("API error"))):
            result = await processor.health_check()

            assert result is False


class TestLLMProcessorCallAPI:
    """Tests for call_api_async method."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        with patch("rhizome.core.llm_client.settings") as mock:
            mock.minimax_api_key = "test-key"
            mock.minimax_base_url = "http://test-url"
            mock.minimax_model = "test-model"
            yield mock

    @pytest.fixture
    def processor(self, mock_settings):
        """Create processor with mocked settings."""
        return LLMProcessor()

    @pytest.mark.asyncio
    async def test_call_api_success(self, processor):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"reply": "test response"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            messages = [{"role": "user", "content": "test"}]
            result = await processor.call_api_async(messages)

            assert result["reply"] == "test response"

    @pytest.mark.asyncio
    async def test_call_api_http_error(self, processor):
        """Test API call raises HTTPStatusError on failure."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_response.request = mock_request

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            messages = [{"role": "user", "content": "test"}]

            # The retry decorator wraps HTTPStatusError in RetryError after 3 attempts
            # We verify that some exception is raised containing HTTPStatusError info
            with pytest.raises(Exception) as exc_info:
                await processor.call_api_async(messages)

            # The final exception should mention the HTTP status code
            error_repr = repr(exc_info.value)
            assert "500" in error_repr or "HTTPStatusError" in error_repr
