"""FastAPI dependencies."""

from typing import AsyncGenerator

from fastapi import Request

from rhizome.core.node_store import NodeStore
from rhizome.retrieval.vector_store import VectorStore, get_vector_store
from rhizome.retrieval.query_engine import QueryEngine


async def get_node_store(request: Request) -> AsyncGenerator[NodeStore, None]:
    """Get NodeStore instance."""
    yield NodeStore()


async def get_vector_store_dep(request: Request) -> AsyncGenerator[VectorStore, None]:
    """Get VectorStore instance."""
    yield get_vector_store()


async def get_query_engine(request: Request) -> AsyncGenerator[QueryEngine, None]:
    """Get QueryEngine instance."""
    vector_store = get_vector_store()
    node_store = NodeStore()
    yield QueryEngine(vector_store=vector_store, node_store=node_store)
