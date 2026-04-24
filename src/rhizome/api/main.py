"""FastAPI application for Rhizome Thinking."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from rhizome.config import settings
from rhizome.api.routes import nodes, query, links, stats, sources, themes, search_stream, search_optimized, outline, epistemic_map, graph_view


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    settings.ensure_directories()
    yield
    # Shutdown


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Rhizome Thinking API",
        description="Personal knowledge base with semantic retrieval",
        version="0.2.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(nodes.router, prefix="/api/v1", tags=["nodes"])
    app.include_router(query.router, prefix="/api/v1", tags=["query"])
    app.include_router(links.router, prefix="/api/v1", tags=["links"])
    app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
    app.include_router(sources.router, prefix="/api/v1", tags=["sources"])
    app.include_router(themes.router, prefix="/api/v1", tags=["themes"])
    app.include_router(search_stream.router, prefix="/api/v1", tags=["search"])
    app.include_router(search_optimized.router, prefix="/api/v1", tags=["search_optimized"])
    app.include_router(outline.router, prefix="/api/v1", tags=["outline"])
    app.include_router(epistemic_map.router, prefix="/api/v1", tags=["epistemic_map"])
    app.include_router(graph_view.router, prefix="/api/v1", tags=["graph_view"])
    
    # Mount static files
    try:
        app.mount("/static", StaticFiles(directory="src/rhizome/web/static"), name="static")
    except RuntimeError:
        # Static directory might not exist yet
        pass
    
    # Root endpoint - serve PWA
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the PWA frontend."""
        try:
            with open("src/rhizome/web/templates/index.html", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Rhizome Thinking</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
            </head>
            <body>
                <h1>Rhizome Thinking</h1>
                <p>Frontend not built yet. API is available at /api/v1/</p>
            </body>
            </html>
            """
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": "0.2.0"}
    
    return app


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
