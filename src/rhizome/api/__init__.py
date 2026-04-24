"""FastAPI web service for Rhizome Thinking (Stage 2)."""

# Lazy import to avoid dependency errors when Stage 2 dependencies are not installed
__all__ = ["create_app"]

def __getattr__(name: str):
    """Lazy import to avoid loading heavy dependencies unless needed."""
    if name == "create_app":
        from rhizome.api.main import create_app
        return create_app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
