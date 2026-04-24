"""Vector storage implementation using ChromaDB and MiniMax Embedding API."""

import hashlib
import json
from typing import Optional, Union
from datetime import datetime, timedelta

import httpx
import chromadb
from chromadb.config import Settings as ChromaSettings
from tenacity import retry, stop_after_attempt, wait_exponential

from rhizome.config import settings
from rhizome.core.models import Node


class MockEmbeddingGenerator:
    """Mock embedding generator for testing without API calls."""
    
    EMBEDDING_DIM = 1536  # Same dimension as MiniMax embeddings
    
    def __init__(self, *args, **kwargs) -> None:
        """Initialize mock generator - ignores all parameters."""
        pass
    
    def _generate_mock_embedding(self, text: str) -> list[float]:
        """Generate a deterministic mock embedding from text.
        
        Uses hash of text to generate consistent embeddings.
        """
        # Create a deterministic seed from text
        hash_obj = hashlib.md5(text.encode('utf-8'))
        seed = int(hash_obj.hexdigest(), 16)
        
        # Generate pseudo-random but deterministic embedding
        import random
        rng = random.Random(seed)
        
        # Generate normalized random vector
        embedding = [rng.uniform(-1, 1) for _ in range(self.EMBEDDING_DIM)]
        
        # Normalize to unit length
        import math
        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
    
    async def get_embedding(self, text: str, emb_type: str = "db") -> list[float]:
        """Get mock embedding vector for text."""
        return self._generate_mock_embedding(text)
    
    async def get_embeddings_batch(self, texts: list[str], emb_type: str = "db") -> list[list[float]]:
        """Get mock embeddings for multiple texts."""
        return [self._generate_mock_embedding(text) for text in texts]


class SiliconFlowEmbeddingGenerator:
    """Generates embeddings using SiliconFlow Embedding API (OpenAI compatible)."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> None:
        """Initialize the embedding generator.
        
        Args:
            api_key: SiliconFlow API key
            base_url: SiliconFlow API base URL
            model: Embedding model name
        """
        self.api_key = api_key or settings.siliconflow_api_key
        self.base_url = base_url or settings.siliconflow_base_url
        self.model = model or settings.siliconflow_embedding_model
        
        if not self.api_key:
            raise ValueError("SiliconFlow API key is required for embedding generation.")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_embedding(self, text: str, emb_type: str = "db") -> list[float]:
        """Get embedding vector for text.
        
        Args:
            text: Text to embed
            emb_type: Type of embedding - ignored for SiliconFlow (OpenAI compatible)
            
        Returns:
            Embedding vector
        """
        url = f"{self.base_url}/embeddings"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # SiliconFlow uses OpenAI compatible format
        payload = {
            "model": self.model,
            "input": text,
            "encoding_format": "float"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract embedding from response - OpenAI format returns 'data'
            embeddings = data.get("data", [])
            if not embeddings:
                raise ValueError("No embeddings in API response")
            
            return embeddings[0].get("embedding", [])
    
    async def get_embeddings_batch(self, texts: list[str], emb_type: str = "db") -> list[list[float]]:
        """Get embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            emb_type: Type of embedding - ignored for SiliconFlow
            
        Returns:
            List of embedding vectors
        """
        url = f"{self.base_url}/embeddings"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # SiliconFlow uses OpenAI compatible format
        payload = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float"
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # OpenAI format returns 'data' with embedding objects
            embeddings = data.get("data", [])
            return [e.get("embedding", []) for e in embeddings]


class VectorStore:
    """Manages vector storage and retrieval using ChromaDB."""
    
    COLLECTION_NAME = "nodes"
    
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        embedding_generator: Optional[Union[MockEmbeddingGenerator, SiliconFlowEmbeddingGenerator]] = None
    ) -> None:
        """Initialize the vector store.

        Args:
            persist_dir: Directory to persist ChromaDB data
            embedding_generator: Embedding generator instance
        """
        self.persist_dir = str(persist_dir or settings.chroma_persist_dir)
        if embedding_generator is not None:
            self.embedding_generator = embedding_generator
        elif settings.use_mock_embedding:
            self.embedding_generator = MockEmbeddingGenerator()
        else:
            self.embedding_generator = SiliconFlowEmbeddingGenerator()
        
        # Initialize ChromaDB client
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Rhizome knowledge base nodes"}
        )
    
    def _node_to_document(self, node: Node) -> str:
        """Convert node to document text for embedding.
        
        Args:
            node: The node
            
        Returns:
            Document text combining proposition and raw input
        """
        parts = [
            f"核心命题: {node.processed.proposition}",
            f"原始输入: {node.raw_input}"
        ]
        if node.processed.open_questions:
            parts.append(f"开放问题: {' '.join(node.processed.open_questions)}")
        return "\n".join(parts)
    
    def _node_to_metadata(self, node: Node) -> dict:
        """Convert node to metadata dictionary.
        
        Args:
            node: The node
            
        Returns:
            Metadata dictionary
        """
        return {
            "proposition": node.processed.proposition,
            "tags": json.dumps(node.tags),
            "timestamp": node.timestamp.isoformat(),
            "source_type": node.source.type,
            "source_title": node.source.title or "",
            "link_count": len(node.links)
        }
    
    async def add_node(self, node: Node) -> None:
        """Add or update a node in the vector store.
        
        Args:
            node: The node to add
        """
        # Generate embedding if not present
        if not node.embedding:
            document = self._node_to_document(node)
            embedding = await self.embedding_generator.get_embedding(document)
            node.embedding = embedding
        
        # Add to collection
        self._collection.upsert(
            ids=[node.id],
            embeddings=[node.embedding],
            metadatas=[self._node_to_metadata(node)],
            documents=[self._node_to_document(node)]
        )
    
    async def add_nodes_batch(self, nodes: list[Node], batch_size: int = 10) -> None:
        """Add multiple nodes in batches.
        
        Args:
            nodes: List of nodes to add
            batch_size: Number of nodes to process in each batch
        """
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            
            # Generate embeddings for nodes without them
            texts_to_embed = []
            nodes_to_embed = []
            
            for node in batch:
                if not node.embedding:
                    texts_to_embed.append(self._node_to_document(node))
                    nodes_to_embed.append(node)
            
            if texts_to_embed:
                embeddings = await self.embedding_generator.get_embeddings_batch(texts_to_embed)
                for node, embedding in zip(nodes_to_embed, embeddings):
                    node.embedding = embedding
            
            # Add to collection
            self._collection.upsert(
                ids=[n.id for n in batch],
                embeddings=[n.embedding for n in batch],
                metadatas=[self._node_to_metadata(n) for n in batch],
                documents=[self._node_to_document(n) for n in batch]
            )
    
    async def search(
        self,
        query: str,
        limit: int = 20,
        tags: Optional[list[str]] = None,
        time_range: Optional[str] = None
    ) -> list[tuple[str, float, dict]]:
        """Search for similar nodes.
        
        Args:
            query: Query text (semantic anchor)
            limit: Maximum number of results
            tags: Filter by tags
            time_range: Time range filter (e.g., "last_week", "last_month")
            
        Returns:
            List of (node_id, similarity_score, metadata) tuples
        """
        # Build where clause
        where_clause = self._build_where_clause(tags, time_range)
        
        # Generate query embedding - use 'query' type for search
        query_embedding = await self.embedding_generator.get_embedding(query, emb_type="query")
        
        # Query collection
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where_clause if where_clause else None
        )
        
        # Format results
        formatted_results = []
        if results["ids"] and results["ids"][0]:
            for i, node_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0.0
                # ChromaDB returns L2 distance (Euclidean)
                # Convert to similarity score using exponential decay for more natural distribution
                # Higher distance = lower similarity
                # 使用指数衰减函数，使相似度分布更平滑，避免阈值边界过于陡峭
                import math
                similarity_score = max(0.0, math.exp(-distance / 0.8))  # 0.8 是衰减系数
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                formatted_results.append((node_id, similarity_score, metadata))
        
        # 添加调试日志，帮助理解相似度分布
        if formatted_results:
            scores = [s for _, s, _ in formatted_results]
            print(f"[Vector Search Debug] Query: '{query[:50]}...', "
                  f"Results: {len(formatted_results)}, "
                  f"Score range: {min(scores):.3f} - {max(scores):.3f}, "
                  f"Avg: {sum(scores)/len(scores):.3f}")
        
        return formatted_results
    
    def _build_where_clause(
        self,
        tags: Optional[list[str]] = None,
        time_range: Optional[str] = None
    ) -> Optional[dict]:
        """Build ChromaDB where clause from filters.
        
        Args:
            tags: Tags to filter by
            time_range: Time range filter
            
        Returns:
            Where clause dictionary or None
        """
        conditions = []
        
        # Tag filter - note: ChromaDB doesn't support array contains directly
        # We'll filter tags in post-processing for now
        
        # Time range filter
        if time_range:
            now = datetime.now()
            if time_range == "last_week":
                cutoff = now - timedelta(days=7)
            elif time_range == "last_month":
                cutoff = now - timedelta(days=30)
            elif time_range == "last_3_months":
                cutoff = now - timedelta(days=90)
            else:
                cutoff = None
            
            if cutoff:
                conditions.append({
                    "timestamp": {"$gte": cutoff.isoformat()}
                })
        
        if not conditions:
            return None
        
        if len(conditions) == 1:
            return conditions[0]
        
        return {"$and": conditions}
    
    def delete_node(self, node_id: str) -> None:
        """Delete a node from the vector store.
        
        Args:
            node_id: ID of the node to delete
        """
        self._collection.delete(ids=[node_id])
    
    def get_stats(self) -> dict:
        """Get statistics about the vector store.
        
        Returns:
            Dictionary with statistics
        """
        count = self._collection.count()
        return {
            "total_vectors": count,
            "collection_name": self.COLLECTION_NAME
        }
    
    def clear(self) -> None:
        """Clear all vectors from the collection."""
        self._collection.delete(where={})


# Global vector store instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store instance.
    
    Returns:
        VectorStore instance
    """
    global _vector_store
    if _vector_store is None:
        # Choose embedding generator based on configuration
        if settings.use_mock_embedding:
            embedding_generator = MockEmbeddingGenerator()
        else:
            embedding_generator = SiliconFlowEmbeddingGenerator()
        
        _vector_store = VectorStore(embedding_generator=embedding_generator)
    return _vector_store
