"""Tests for query engine."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from rhizome.core.models import Node, Processed, Source, Link
from rhizome.retrieval.query_engine import QueryEngine, QueryModifiers, QueryResult


class TestQueryModifiers:
    """Tests for QueryModifiers parsing."""

    def test_default_values(self):
        """Test QueryModifiers default values."""
        modifiers = QueryModifiers()
        assert modifiers.time_range == "all"
        assert modifiers.tags == []
        assert modifiers.relation_type is None
        assert modifiers.limit == 20

    def test_with_tags(self):
        """Test QueryModifiers with tags."""
        modifiers = QueryModifiers(tags=["definitive", "inferred"])
        assert modifiers.tags == ["definitive", "inferred"]

    def test_with_time_range(self):
        """Test QueryModifiers with time_range."""
        modifiers = QueryModifiers(time_range="last_month")
        assert modifiers.time_range == "last_month"

    def test_with_limit(self):
        """Test QueryModifiers with custom limit."""
        modifiers = QueryModifiers(limit=50)
        assert modifiers.limit == 50

    def test_limit_validation(self):
        """Test limit must be between 1 and 100."""
        with pytest.raises(Exception):  # Pydantic validation error
            QueryModifiers(limit=0)
        with pytest.raises(Exception):
            QueryModifiers(limit=101)

    def test_json_schema_extra(self):
        """Test example schema is present."""
        assert QueryModifiers.model_config.get("json_schema_extra") is not None


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_query_result_creation(self):
        """Test QueryResult creation."""
        node = Node(
            raw_input="test",
            processed=Processed(proposition="test proposition")
        )
        result = QueryResult(node=node, similarity=0.95, highlight="test highlight")

        assert result.node == node
        assert result.similarity == 0.95
        assert result.highlight == "test highlight"

    def test_query_result_default_highlight(self):
        """Test QueryResult default highlight is None."""
        node = Node(
            raw_input="test",
            processed=Processed(proposition="test proposition")
        )
        result = QueryResult(node=node, similarity=0.95)

        assert result.highlight is None


class TestQueryEngineGroupByTags:
    """Tests for group_by_tags functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = QueryEngine()

        # Create test nodes with different tags
        self.node_definitive = Node(
            raw_input="def input",
            processed=Processed(proposition="def proposition"),
            tags=["definitive"]
        )
        self.node_vague = Node(
            raw_input="vague input",
            processed=Processed(proposition="vague proposition"),
            tags=["vague"]
        )
        self.node_multi_tags = Node(
            raw_input="multi input",
            processed=Processed(proposition="multi proposition"),
            tags=["definitive", "cross-domain"]
        )

    def test_group_by_tags_empty(self):
        """Test grouping empty results."""
        grouped = self.engine.group_by_tags([])

        assert grouped == {}

    def test_group_by_tags_single_tag(self):
        """Test grouping results with single tags."""
        results = [
            QueryResult(node=self.node_definitive, similarity=0.9),
            QueryResult(node=self.node_vague, similarity=0.8),
        ]

        grouped = self.engine.group_by_tags(results)

        assert "明确结论" in grouped
        assert "模糊感知" in grouped
        assert len(grouped["明确结论"]) == 1
        assert len(grouped["模糊感知"]) == 1

    def test_group_by_tags_multi_tags(self):
        """Test grouping results with multiple tags."""
        results = [
            QueryResult(node=self.node_multi_tags, similarity=0.95),
        ]

        grouped = self.engine.group_by_tags(results)

        # Node with multiple tags appears in both groups
        assert "明确结论" in grouped
        assert "跨域连接" in grouped
        assert len(grouped["明确结论"]) == 1
        assert len(grouped["跨域连接"]) == 1

    def test_group_by_tags_ordered(self):
        """Test that groups maintain tag order."""
        results = [
            QueryResult(node=self.node_vague, similarity=0.8),
            QueryResult(node=self.node_definitive, similarity=0.9),
        ]

        grouped = self.engine.group_by_tags(results)

        # Check order: definitive -> inferred -> vague -> needs_thinking -> cross-domain
        keys = list(grouped.keys())
        assert "明确结论" in keys
        assert "模糊感知" in keys

    def test_group_by_tags_no_empty_groups(self):
        """Test that empty groups are not included."""
        results = [
            QueryResult(node=self.node_definitive, similarity=0.9),
        ]

        grouped = self.engine.group_by_tags(results)

        # Only definitive should be present, others should be filtered out
        assert len(grouped) == 1
        assert "明确结论" in grouped


class TestQueryEngineGroupByTime:
    """Tests for group_by_time functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = QueryEngine()

    def test_group_by_time_empty(self):
        """Test grouping empty results."""
        grouped = self.engine.group_by_time([])

        assert grouped == {}

    def test_group_by_time_this_week(self):
        """Test grouping results from this week."""
        node = Node(
            raw_input="recent",
            processed=Processed(proposition="recent proposition"),
            timestamp=datetime.now() - timedelta(days=2)
        )
        results = [QueryResult(node=node, similarity=0.9)]

        grouped = self.engine.group_by_time(results)

        assert "本周" in grouped
        assert len(grouped["本周"]) == 1

    def test_group_by_time_this_month(self):
        """Test grouping results from this month."""
        node = Node(
            raw_input="month",
            processed=Processed(proposition="month proposition"),
            timestamp=datetime.now() - timedelta(days=15)
        )
        results = [QueryResult(node=node, similarity=0.9)]

        grouped = self.engine.group_by_time(results)

        assert "本月" in grouped
        assert len(grouped["本月"]) == 1

    def test_group_by_time_last_3_months(self):
        """Test grouping results from last 3 months."""
        node = Node(
            raw_input="3months",
            processed=Processed(proposition="3months proposition"),
            timestamp=datetime.now() - timedelta(days=60)
        )
        results = [QueryResult(node=node, similarity=0.9)]

        grouped = self.engine.group_by_time(results)

        assert "近3个月" in grouped
        assert len(grouped["近3个月"]) == 1

    def test_group_by_time_older(self):
        """Test grouping results older than 3 months."""
        node = Node(
            raw_input="older",
            processed=Processed(proposition="older proposition"),
            timestamp=datetime.now() - timedelta(days=100)
        )
        results = [QueryResult(node=node, similarity=0.9)]

        grouped = self.engine.group_by_time(results)

        assert "更早" in grouped
        assert len(grouped["更早"]) == 1


class TestQueryEngineSearch:
    """Tests for search functionality."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        mock.get_stats = MagicMock(return_value={"total": 0})
        return mock

    @pytest.fixture
    def mock_node_store(self):
        """Create a mock node store."""
        mock = MagicMock()
        mock.get = MagicMock(return_value=None)
        mock.get_stats = MagicMock(return_value={"total": 0})
        return mock

    @pytest.fixture
    def engine(self, mock_vector_store, mock_node_store):
        """Create a query engine with mock stores."""
        return QueryEngine(
            vector_store=mock_vector_store,
            node_store=mock_node_store
        )

    @pytest.mark.asyncio
    async def test_search_no_results(self, engine, mock_vector_store, mock_node_store):
        """Test search with no results."""
        mock_vector_store.search.return_value = []

        results = await engine.search("test query")

        assert results == []
        mock_vector_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_tag_filter(self, engine, mock_vector_store, mock_node_store):
        """Test search with tag filtering."""
        node = Node(
            raw_input="test",
            processed=Processed(proposition="test proposition"),
            tags=["definitive"]
        )

        mock_vector_store.search.return_value = [
            ("node-id-1", 0.95, {})
        ]
        mock_node_store.get.return_value = node

        modifiers = QueryModifiers(tags=["definitive"])
        results = await engine.search("test query", modifiers)

        assert len(results) == 1
        assert results[0].node == node

    @pytest.mark.asyncio
    async def test_search_tag_filter_no_match(self, engine, mock_vector_store, mock_node_store):
        """Test search when tag filter doesn't match."""
        node = Node(
            raw_input="test",
            processed=Processed(proposition="test proposition"),
            tags=["definitive"]
        )

        mock_vector_store.search.return_value = [
            ("node-id-1", 0.95, {})
        ]
        mock_node_store.get.return_value = node

        modifiers = QueryModifiers(tags=["vague"])
        results = await engine.search("test query", modifiers)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_with_time_range(self, engine, mock_vector_store):
        """Test search with time_range filter."""
        modifiers = QueryModifiers(time_range="last_month")

        await engine.search("test query", modifiers)

        mock_vector_store.search.assert_called_once()
        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["time_range"] == "last_month"

    @pytest.mark.asyncio
    async def test_search_time_range_all(self, engine, mock_vector_store):
        """Test search with time_range=all passes None to vector store."""
        modifiers = QueryModifiers(time_range="all")

        await engine.search("test query", modifiers)

        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["time_range"] is None

    @pytest.mark.asyncio
    async def test_search_relation_type_filter(self, engine, mock_vector_store, mock_node_store):
        """Test search with relation type filtering."""
        node = Node(
            raw_input="test",
            processed=Processed(proposition="test proposition"),
            links=[Link(target_id="other", relation_type="support", strength=0.8)]
        )

        mock_vector_store.search.return_value = [
            ("node-id-1", 0.95, {})
        ]
        mock_node_store.get.return_value = node

        modifiers = QueryModifiers(relation_type="support")
        results = await engine.search("test query", modifiers)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_relation_type_no_match(self, engine, mock_vector_store, mock_node_store):
        """Test search when relation type doesn't match."""
        node = Node(
            raw_input="test",
            processed=Processed(proposition="test proposition"),
            links=[Link(target_id="other", relation_type="support", strength=0.8)]
        )

        mock_vector_store.search.return_value = [
            ("node-id-1", 0.95, {})
        ]
        mock_node_store.get.return_value = node

        modifiers = QueryModifiers(relation_type="contradict")
        results = await engine.search("test query", modifiers)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, engine, mock_vector_store, mock_node_store):
        """Test search respects the limit modifier."""
        nodes = [
            Node(raw_input=f"test-{i}", processed=Processed(proposition=f"prop-{i}"))
            for i in range(5)
        ]

        mock_vector_store.search.return_value = [
            (f"node-id-{i}", 0.9 - i * 0.01, {}) for i in range(5)
        ]
        mock_node_store.get.side_effect = nodes

        modifiers = QueryModifiers(limit=3)
        results = await engine.search("test query", modifiers)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_handles_missing_node(self, engine, mock_vector_store, mock_node_store):
        """Test search handles node not found in node store."""
        mock_vector_store.search.return_value = [
            ("node-id-1", 0.95, {}),
            ("node-id-2", 0.90, {}),
        ]
        mock_node_store.get.side_effect = [None, Node(
            raw_input="test",
            processed=Processed(proposition="test proposition")
        )]

        results = await engine.search("test query")

        # Only 1 result since first node was not found
        assert len(results) == 1


class TestQueryEngineRelatedNodes:
    """Tests for get_related_nodes functionality."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_node_store(self):
        """Create a mock node store."""
        mock = MagicMock()
        return mock

    @pytest.fixture
    def engine(self, mock_vector_store, mock_node_store):
        """Create a query engine with mock stores."""
        return QueryEngine(
            vector_store=mock_vector_store,
            node_store=mock_node_store
        )

    @pytest.mark.asyncio
    async def test_get_related_nodes_not_found(self, engine, mock_node_store):
        """Test get_related_nodes when node doesn't exist."""
        mock_node_store.get.return_value = None

        results = await engine.get_related_nodes("non-existent-id")

        assert results == []

    @pytest.mark.asyncio
    async def test_get_related_nodes_excludes_self(self, engine, mock_node_store, mock_vector_store):
        """Test get_related_nodes excludes the source node."""
        source_node = Node(
            id="source-id",
            raw_input="source",
            processed=Processed(proposition="source proposition")
        )
        related_node = Node(
            id="related-id",
            raw_input="related",
            processed=Processed(proposition="related proposition")
        )

        # get() is called first to get the source node, then again inside search() for each result
        # Call 1: get_related_nodes gets source node
        # Call 2-3: search() loads nodes from vector results (source, related)
        mock_node_store.get.side_effect = [
            source_node,  # get_related_nodes initial lookup
            source_node,  # search() loads source-id
            related_node,  # search() loads related-id
        ]
        mock_vector_store.search.return_value = [
            ("source-id", 1.0, {}),
            ("related-id", 0.9, {}),
        ]

        results = await engine.get_related_nodes("source-id")

        # Should only return 1 result (related), not the source node itself
        assert len(results) == 1
        assert results[0].node.raw_input == "related"


class TestQueryEngineStats:
    """Tests for get_stats functionality."""

    def test_get_stats(self):
        """Test get_stats returns combined stats."""
        mock_vector_store = MagicMock()
        mock_vector_store.get_stats.return_value = {"vectors": 100}

        mock_node_store = MagicMock()
        mock_node_store.get_stats.return_value = {"nodes": 50}

        engine = QueryEngine(
            vector_store=mock_vector_store,
            node_store=mock_node_store
        )

        stats = engine.get_stats()

        assert "vector_store" in stats
        assert "node_store" in stats
        assert stats["vector_store"]["vectors"] == 100
        assert stats["node_store"]["nodes"] == 50


class TestGenerateHighlight:
    """Tests for _generate_highlight functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = QueryEngine()

    def test_generate_highlight_short(self):
        """Test highlight for short proposition."""
        node = Node(
            raw_input="test",
            processed=Processed(proposition="Short proposition")
        )

        highlight = self.engine._generate_highlight(node, "test query")

        assert highlight == "Short proposition"

    def test_generate_highlight_long(self):
        """Test highlight truncation for long proposition."""
        long_proposition = "A" * 200
        node = Node(
            raw_input="test",
            processed=Processed(proposition=long_proposition)
        )

        highlight = self.engine._generate_highlight(node, "test query")

        # 150 chars + "..." = 153 chars
        assert len(highlight) == 153
        assert highlight.endswith("...")
