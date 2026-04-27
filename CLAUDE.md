# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rhizome-thinking is a personal knowledge base system. Users input notes, and the system auto-classifies them with tags, extracts themes, builds semantic links between nodes, and supports full-text and semantic search. Three-stage plan — Stage 2 is complete, Stage 3 (epistemic map) is in progress:

- **Stage 1**: CLI pipe validation — Markdown storage + LLM processing
- **Stage 2**: Semantic retrieval with ChromaDB + FastAPI + PWA frontend
- **Stage 3**: Graphical epistemic map view (API endpoints exist, frontend WIP)

## Architecture

```
Single Docker container:
  uvicorn (0.0.0.0:8000)
    ├── FastAPI API (/api/v1/*)
    ├── ChromaDB (embedded PersistentClient, /app/storage/chroma/)
    └── PWA frontend (/)

src/rhizome/
├── core/
│   ├── models.py           # Node, Link, Source, Processed pydantic dataclasses
│   ├── node_store.py        # Markdown file storage + search
│   ├── llm_processor.py     # MiniMax API for LLM processing
│   ├── theme_models.py      # Theme, NodeTheme pydantic models
│   ├── theme_store.py       # Theme persistence (JSON files + index)
│   ├── theme_extractor.py   # LLM-driven theme extraction from nodes
│   ├── backup_manager.py    # ZIP backup/restore (nodes, metadata, themes)
│   └── source_config.py     # Source type configuration
├── api/
│   ├── main.py              # FastAPI app factory, static mount, health, 12 route modules
│   └── routes/              # nodes, query, links, stats, sources, themes,
│                            #   search_stream, search_optimized, outline,
│                            #   epistemic_map, graph_view, backup
├── retrieval/
│   ├── vector_store.py      # ChromaDB PersistentClient + SiliconFlow embeddings
│   ├── query_engine.py      # Semantic search with QueryModifiers
│   ├── search_optimizer.py  # Theme-aware caching + reranking for search
│   └── llm_search.py        # LLM-powered theme-aware search
├── web/
│   ├── templates/index.html # PWA single-page app
│   └── static/              # css/style.css, js/app.js, js/views.js, js/sw.js,
│                            #   manifest.json, images/icons/
├── cli.py                   # Click-based CLI (rhz command, 20+ subcommands)
└── config.py                # pydantic-settings, reads .env
```

**Key data flow**: Raw input → LLMProcessor (MiniMax API) → Node (YAML frontmatter + Markdown) → ThemeExtractor → Theme JSON files. Query path: user query → search_optimizer (loads themes+cache) → llm_search (LLM rerank) → results.

## Commands

```bash
# Install (editable, inside venv)
pip install -e ".[stage2]"     # Full: FastAPI + ChromaDB + CLI
pip install -e ".[dev]"        # Includes pytest, ruff, mypy, black

# CLI (installed as 'rhz', or python -m rhizome)
rhz add "note content"          # Add node (LLM processing)
rhz add -f note.txt             # Add from file
rhz list                        # List nodes
rhz list -t needs_thinking      # Filter by tag
rhz show <node-id>              # Show node detail (supports prefix match)
rhz stats                       # Knowledge base stats
rhz search "keywords"           # Proposition text search (Stage 1)
rhz query "semantic query"      # Semantic search with ChromaDB (Stage 2)
rhz query "..." -t cross-domain --time-range last_month
rhz find --proposition "..." --tag needs_thinking --from-date 2026-01-01
rhz edit <node-id> --tags "needs_thinking,cross-domain"
rhz delete <node-id> --force
rhz vectorize                   # Batch-embed all nodes into ChromaDB
rhz link confirm <id> <target>  # Confirm pending link
rhz link reject <id> <target>   # Reject pending link
rhz link add <id> <target> -t support -s 0.8  # Manual link
rhz backup create               # Create ZIP backup
rhz backup list                 # List backups
rhz backup restore <name> --force  # Restore from backup
rhz backup delete <name>        # Delete a backup
rhz serve --reload              # Start dev server (direct uvicorn, no Docker)
rhz server start|stop|restart|status|logs|info|config  # Docker management
rhz install                     # Install systemd service (Linux server only)
rhz uninstall                   # Uninstall systemd service

# Tests
pytest tests/ -v
pytest tests/test_models.py -v   # Single test file
```

## Docker Deployment

```bash
# One-time deploy
bash scripts/deploy.sh           # Creates .env, builds image, starts container

# Update
git pull && docker compose up -d --build

# Service management
docker compose up -d             # Start
docker compose down              # Stop
docker compose restart           # Restart
docker compose logs -f           # View logs
```

`docker-compose.yml` mounts `./storage` (rw) and `./.env` (ro) into the container. Container runs as UID 1000 (appuser). Port defaults to 8000, overridable via `PORT` env var.

## Storage Layout

All user data lives in `storage/` (on host, mounted to `/app/storage/` in container):

| Path | Content |
|---|---|
| `storage/nodes/*.md` | Node files (YAML frontmatter + Markdown body) |
| `storage/metadata/nodes_index.json` | Node metadata index |
| `storage/metadata/themes_index.json` | Theme metadata index |
| `storage/metadata/node_themes/*.json` | Per-node theme associations |
| `storage/themes/*.json` | Individual theme objects |
| `storage/chroma/` | ChromaDB embedded data (SQLite + Parquet + HNSW) |
| `storage/backups/*.zip` | Full backups (nodes + metadata + themes) |

Data persists across container rebuilds via the volume mount. **Never commit `storage/` to git.**

## Key Design Decisions

**Tags**: One or more of `definitive`, `inferred`, `vague`, `needs_thinking`, `cross-domain`. CLI maps to Chinese: `needs_thinking`→需要思考, `vague`→模糊, etc.

**Links**: Nodes connect via `support`, `contradict`, `extend`, `source`, `analogy` relation types. Links can be `confirmed` or `pending` (unconfirmed from LLM suggestions).

**Themes**: LLM extracts cross-node themes. Stored as individual JSON files in `themes/` directory + indexed in `metadata/themes_index.json`. `get_all_themes()` reads from individual files — the index alone is insufficient. Theme-aware search uses ThemeDataCache which filters themes by tag/time then reranks via LLM.

**Backup**: `BackupManager.backup()` creates ZIP containing `nodes/`, `metadata/` (root JSONs + node_themes/), and `themes/`. Restore clears existing data then extracts all paths from the ZIP. Vector/chroma data is NOT included (too large, can be regenerated via `rhz vectorize`).

**API Keys**: `.env` file (not committed). MiniMax for LLM processing (`MINIMAX_API_KEY`), SiliconFlow for embeddings (`SILICONFLOW_API_KEY`). Set `USE_MOCK_EMBEDDING=true` for offline testing.

**Interface language**: CLI output uses Chinese; code, comments, API paths/params use English.

**PWA**: Service Worker requires HTTPS — won't register on LAN HTTP. All online features work without it. Fonts load from Google Fonts CDN; degrade to system fonts if network is unavailable.
