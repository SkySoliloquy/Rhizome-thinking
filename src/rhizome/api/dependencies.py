"""FastAPI dependencies with singleton caching."""

from typing import AsyncGenerator

from fastapi import Request

from rhizome.core.node_store import NodeStore
from rhizome.retrieval.vector_store import VectorStore, get_vector_store
from rhizome.retrieval.query_engine import QueryEngine

# Singleton instances - created once and reused across requests
_node_store: NodeStore | None = None
_query_engine: QueryEngine | None = None


def _get_node_store_singleton() -> NodeStore:
    global _node_store
    if _node_store is None:
        _node_store = NodeStore()
    return _node_store


def _get_query_engine_singleton() -> QueryEngine:
    global _query_engine
    if _query_engine is None:
        vector_store = get_vector_store()
        node_store = _get_node_store_singleton()
        _query_engine = QueryEngine(vector_store=vector_store, node_store=node_store)
    return _query_engine


async def get_node_store(request: Request) -> AsyncGenerator[NodeStore, None]:
    """Get NodeStore singleton instance."""
    yield _get_node_store_singleton()


async def get_vector_store_dep(request: Request) -> AsyncGenerator[VectorStore, None]:
    """Get VectorStore singleton instance."""
    yield get_vector_store()


async def get_query_engine(request: Request) -> AsyncGenerator[QueryEngine, None]:
    """Get QueryEngine singleton instance."""
    yield _get_query_engine_singleton()
