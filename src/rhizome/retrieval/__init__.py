"""Retrieval module for semantic search (Stage 2)."""

# Lazy imports to avoid dependency errors when Stage 2 dependencies are not installed
# Use: from rhizome.retrieval import VectorStore

__all__ = [
    "VectorStore",
    "get_vector_store",
    "QueryEngine",
    "QueryModifiers",
    "QueryResult",
]

def __getattr__(name: str):
    """Lazy import to avoid loading heavy dependencies unless needed."""
    if name in ("VectorStore", "get_vector_store"):
        from rhizome.retrieval.vector_store import VectorStore, get_vector_store
        return locals()[name]
    elif name in ("QueryEngine", "QueryModifiers", "QueryResult"):
        from rhizome.retrieval.query_engine import QueryEngine, QueryModifiers, QueryResult
        return locals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
