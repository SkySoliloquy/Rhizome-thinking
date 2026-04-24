"""Tests for node storage."""

import pytest
from pathlib import Path

from rhizome.core.models import Node, Processed, Source, Link
from rhizome.core.node_store import NodeStore


class TestNodeStore:
    @pytest.fixture
    def temp_store(self, tmp_path):
        """Create a temporary node store."""
        return NodeStore(storage_dir=tmp_path)
    
    @pytest.fixture
    def sample_node(self):
        """Create a sample node."""
        return Node(
            raw_input="Test input",
            processed=Processed(proposition="Test proposition"),
            tags=["definitive"],
            source=Source(type="original")
        )
    
    def test_store_initialization(self, tmp_path):
        store = NodeStore(storage_dir=tmp_path)
        assert store.nodes_dir.exists()
        assert store.metadata_dir.exists()
    
    def test_save_and_get(self, temp_store, sample_node):
        # Save node
        temp_store.save(sample_node)
        
        # Retrieve node
        retrieved = temp_store.get(sample_node.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_node.id
        assert retrieved.raw_input == sample_node.raw_input
        assert retrieved.processed.proposition == sample_node.processed.proposition
    
    def test_exists(self, temp_store, sample_node):
        assert not temp_store.exists(sample_node.id)
        
        temp_store.save(sample_node)
        
        assert temp_store.exists(sample_node.id)
    
    def test_delete(self, temp_store, sample_node):
        temp_store.save(sample_node)
        assert temp_store.exists(sample_node.id)
        
        result = temp_store.delete(sample_node.id)
        
        assert result is True
        assert not temp_store.exists(sample_node.id)
    
    def test_delete_nonexistent(self, temp_store):
        result = temp_store.delete("nonexistent-id")
        assert result is False
    
    def test_list_all(self, temp_store):
        # Create multiple nodes
        for i in range(5):
            node = Node(
                raw_input=f"Input {i}",
                processed=Processed(proposition=f"Proposition {i}"),
                tags=["vague"] if i % 2 == 0 else ["definitive"]
            )
            temp_store.save(node)
        
        # List all
        nodes = temp_store.list_all()
        assert len(nodes) == 5
        
        # Test limit
        nodes = temp_store.list_all(limit=3)
        assert len(nodes) == 3
    
    def test_list_by_tag(self, temp_store):
        # Create nodes with different tags
        for i in range(4):
            node = Node(
                raw_input=f"Input {i}",
                processed=Processed(proposition=f"Proposition {i}"),
                tags=["vague"] if i % 2 == 0 else ["definitive"]
            )
            temp_store.save(node)
        
        vague_nodes = temp_store.list_by_tag("vague")
        assert len(vague_nodes) == 2
        
        definitive_nodes = temp_store.list_by_tag("definitive")
        assert len(definitive_nodes) == 2
    
    def test_add_link(self, temp_store):
        # Create two nodes
        node1 = Node(
            raw_input="Input 1",
            processed=Processed(proposition="Proposition 1"),
            tags=["definitive"]
        )
        node2 = Node(
            raw_input="Input 2",
            processed=Processed(proposition="Proposition 2"),
            tags=["inferred"]
        )
        
        temp_store.save(node1)
        temp_store.save(node2)
        
        # Add link
        result = temp_store.add_link(
            node1.id,
            node2.id,
            relation_type="support",
            strength=0.8,
            confirmed=True
        )
        
        assert result is True
        
        # Verify link
        retrieved = temp_store.get(node1.id)
        assert len(retrieved.links) == 1
        assert retrieved.links[0].target_id == node2.id
        assert retrieved.links[0].confirmed is True
    
    def test_update_link(self, temp_store):
        # Create node with link
        node = Node(
            raw_input="Input",
            processed=Processed(proposition="Proposition"),
            tags=["definitive"],
            links=[Link(target_id="target-123", relation_type="analogy", confirmed=False)]
        )
        temp_store.save(node)
        
        # Update link
        result = temp_store.update_link(node.id, "target-123", confirmed=True)
        
        assert result is True
        
        # Verify
        retrieved = temp_store.get(node.id)
        assert retrieved.links[0].confirmed is True
    
    def test_get_stats(self, temp_store):
        # Create nodes
        for i in range(3):
            node = Node(
                raw_input=f"Input {i}",
                processed=Processed(proposition=f"Proposition {i}"),
                tags=["definitive", "cross-domain"][:i+1]
            )
            temp_store.save(node)
        
        stats = temp_store.get_stats()
        
        assert stats["total_nodes"] == 3
        assert "definitive" in stats["tag_counts"]
        assert "cross-domain" in stats["tag_counts"]
    
    def test_search_by_proposition(self, temp_store):
        # Create nodes
        node1 = Node(
            raw_input="Input 1",
            processed=Processed(proposition="Artificial Intelligence is transforming society"),
            tags=["definitive"]
        )
        node2 = Node(
            raw_input="Input 2",
            processed=Processed(proposition="Machine learning requires data"),
            tags=["inferred"]
        )
        
        temp_store.save(node1)
        temp_store.save(node2)
        
        # Search
        results = temp_store.search_by_proposition("Intelligence")
        
        assert len(results) == 1
        assert results[0][0].id == node1.id
    
    def test_markdown_roundtrip(self, temp_store):
        """Test that nodes are correctly saved and loaded from markdown."""
        original = Node(
            raw_input="Test input with special chars: 中文 🎉",
            processed=Processed(
                proposition="Test proposition",
                open_questions=["Question 1?", "Question 2?"]
            ),
            tags=["definitive", "cross-domain"],
            source=Source(type="paper", title="Test Paper"),
            links=[Link(target_id="target-123", relation_type="support", strength=0.9)]
        )
        
        temp_store.save(original)
        retrieved = temp_store.get(original.id)
        
        assert retrieved.raw_input == original.raw_input
        assert retrieved.processed.proposition == original.processed.proposition
        assert retrieved.processed.open_questions == original.processed.open_questions
        assert retrieved.tags == original.tags
        assert retrieved.source.title == original.source.title
        assert len(retrieved.links) == len(original.links)
