# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rhizome-thinking is a personal knowledge base system. Users input notes, and the system auto-classifies them with tags, extracts themes, builds semantic links between nodes, and supports full-text and semantic search. Three-stage plan:

- **Stage 1**: CLI pipe validation — Markdown storage + LLM processing
- **Stage 2**: Semantic retrieval with ChromaDB + FastAPI + PWA frontend
- **Stage 3**: Graphical epistemic map view + AI relationship management + theme evolution (API complete, frontend stable)

## Architecture

```
Single Docker container:
  uvicorn (0.0.0.0:8000)
    ├── FastAPI API (/api/v1/*)
    ├── ChromaDB (embedded PersistentClient, /app/storage/chroma/)
    └── PWA frontend (/)

src/rhizome/
├── core/
│   ├── models.py              # Node, Link, Source, Processed pydantic dataclasses
│   ├── node_store.py          # Markdown file storage + full-text search
│   ├── llm_processor.py       # MiniMax API for LLM processing
│   ├── theme_models.py        # Theme, NodeTheme, ThemeVersion pydantic models
│   ├── theme_store.py         # Theme persistence (JSON files + index)
│   ├── theme_extractor.py     # LLM-driven theme extraction from nodes
│   ├── theme_evolution.py     # Theme evolution tracking (versions, conflicts, suggestions)
│   ├── evolution_store.py     # Theme evolution history persistence
│   ├── relationship_models.py # Relationship, RelationshipType, RelationshipStrength models
│   ├── relationship_store.py  # Relationship persistence (JSON files + index)
│   ├── relationship_manager.py# AI relationship management (suggest, validate, auto-link)
│   ├── backup_manager.py      # ZIP backup/restore (nodes, metadata, themes, relationships)
│   ├── source_config.py       # Source type configuration (built-in + custom)
│   ├── scheduler.py           # Background task scheduler (auto-link, theme evolution, vector sync, backup)
│   └── events.py              # Event bus for decoupled module communication
├── api/
│   ├── main.py                # FastAPI app factory, static mount, health, 14 route modules
│   ├── dependencies.py        # Singleton dependency injection (NodeStore, VectorStore, QueryEngine)
│   └── routes/
│       ├── nodes.py           # Node CRUD
│       ├── query.py           # Semantic search endpoint
│       ├── links.py           # Legacy Node.links management (embedded links)
│       ├── relationships.py   # New independent relationship system (primary)
│       ├── stats.py           # Knowledge base statistics
│       ├── sources.py         # Source type management
│       ├── themes.py          # Theme CRUD
│       ├── theme_evolution.py # Theme evolution API (history, timeline, rollback)
│       ├── search_stream.py   # SSE streaming search with progress updates
│       ├── search_optimized.py# Theme-aware search with strict/balanced/explore modes
│       ├── outline.py         # Knowledge outline generation
│       ├── epistemic_map.py   # Epistemic map data API
│       ├── graph_view.py      # Graph visualization data API
│       └── backup.py          # Backup management (create, restore, download, upload)
├── retrieval/
│   ├── vector_store.py        # ChromaDB PersistentClient + SiliconFlow embeddings
│   ├── query_engine.py        # Semantic search with QueryModifiers
│   ├── search_optimizer.py    # Search cache + parallel theme+vector search
│   └── llm_search.py          # LLM-powered theme reranking
├── web/
│   ├── templates/index.html   # PWA single-page app
│   └── static/                # css/style.css, js/app.js, js/views.js, js/sw.js,
│                              #   manifest.json, images/icons/
├── cli.py                     # Click-based CLI (rhz command, 25+ subcommands)
└── config.py                  # pydantic-settings, reads .env
```

**Key data flows**:

1. **Node creation**: Raw input → LLMProcessor (MiniMax API) → Node (YAML frontmatter + Markdown) → ThemeExtractor → Theme JSON files
2. **Query**: User query → search_optimizer (loads themes+cache) → llm_search (LLM rerank) → results
3. **Relationship management**: Node creation → events (NodeCreatedEvent) → relationship_manager (AI suggest) → relationship_store → relationships/
4. **Theme evolution**: Theme change → theme_evolution (conflict detect) → evolution_store → evolution/
5. **Background tasks**: scheduler triggers auto_link_confirm, theme_evolution_detect, vector_sync, backup_create

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

# Legacy link commands (Node.links embedded, migrating to Relationship system)
rhz link confirm <id> <target>  # Confirm pending link
rhz link reject <id> <target>   # Reject pending link
rhz link add <id> <target> -t support -s 0.8  # Manual link

# New relationship commands (independent Relationship system, preferred)
rhz relationship add <source_id> <target_id> -t supports -s strong --bidirectional
rhz relationship list           # List all relationships
rhz relationship show <id>      # Show relationship detail
rhz relationship delete <id>    # Delete relationship
rhz relationship validate       # Validate relationship integrity
rhz relationship stats          # Relationship statistics
rhz relationship import <file>  # Import from JSON/CSV
rhz relationship export <file>  # Export to JSON/CSV

# Backup commands
rhz backup create               # Create ZIP backup
rhz backup list                 # List backups
rhz backup restore <name> --force  # Restore from backup
rhz backup delete <name>        # Delete a backup

# Server commands
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
| `storage/metadata/source_config.json` | Custom source type configurations |
| `storage/themes/*.json` | Individual theme objects |
| `storage/relationships/*.json` | Individual relationship objects |
| `storage/relationships/relationships_index.json` | Relationship metadata index |
| `storage/evolution/*.json` | Theme evolution history records |
| `storage/chroma/` | ChromaDB embedded data (SQLite + Parquet + HNSW) |
| `storage/backups/*.zip` | Full backups (nodes + metadata + themes + relationships) |
| `storage/scheduler_state.json` | Scheduler state persistence |

Data persists across container rebuilds via the volume mount. **Never commit `storage/` to git.**

## Key Design Decisions

**Tags**: One or more of `definitive`, `inferred`, `vague`, `needs_thinking`, `cross-domain`. CLI maps to Chinese: `needs_thinking`→需要思考, `vague`→模糊, etc.

**Links vs Relationships (Dual Architecture)**:
- **Links** (Legacy): Embedded in the Node model (`Node.links`). Relation types: `support`, `contradict`, `extend`, `source`, `analogy`. Status: `confirmed` or `pending`. Still functional but being superseded.
- **Relationships** (New/Primary): Independent first-class model (`Relationship` in `relationship_models.py`). Relation types: `supports`, `contradicts`, `extends`, `cites`, `analogous_to`. Strength: `strong`, `moderate`, `weak`. Has rich metadata: evidence, notes, directionality, bidirectional flag. Stored in `storage/relationships/` with its own index.
- **Migration status**: Both systems coexist. New features should use the Relationship system. The scheduler's `auto_link_confirm` task bridges between pending Links and confirmed Relationships.

**Themes**: LLM extracts cross-node themes. Stored as individual JSON files in `themes/` directory + indexed in `metadata/themes_index.json`. `get_all_themes()` reads from individual files — the index alone is insufficient. Theme-aware search uses ThemeDataCache which filters themes by tag/time then reranks via LLM.

**Theme Evolution**: Themes support version tracking (`version`, `evolution_history`, `evolution_status`). Evolution status: `stable`, `conflicting`, `evolving`. When new nodes conflict with existing themes, the system generates evolution suggestions. History is preserved in `ThemeVersion` records.

**Search Modes**: The optimized search supports three modes that control result count and relevance threshold:
- `strict`: 2-5 most precise results, only direct matches
- `balanced`: 5-10 results, balance precision and recall (default)
- `explore`: 8-15 results, include weak and indirect associations

**Backup**: `BackupManager.backup()` creates ZIP containing `nodes/`, `metadata/` (root JSONs + node_themes/), `themes/`, and `relationships/`. Restore clears existing data then extracts all paths from the ZIP. Vector/chroma data is NOT included (too large, can be regenerated via `rhz vectorize`).

**Scheduler**: `Scheduler` runs background tasks at configurable intervals:
- `auto_link_confirm`: Converts pending co-occurrence links to confirmed relationships
- `theme_evolution_detect`: Scans for theme conflicts and generates evolution suggestions
- `vector_sync`: Ensures ChromaDB is in sync with node store
- `backup_create`: Periodic full backups

**Events**: `EventBus` provides decoupled communication between modules. Key events: `NodeCreatedEvent`, `NodeUpdatedEvent`, `NodeDeletedEvent`, `ThemeCreatedEvent`, `ThemeUpdatedEvent`, `RelationshipCreatedEvent`. The relationship_manager and theme_extractor subscribe to these events.

**API Keys**: `.env` file (not committed). MiniMax for LLM processing (`MINIMAX_API_KEY`), SiliconFlow for embeddings (`SILICONFLOW_API_KEY`). Set `USE_MOCK_EMBEDDING=true` for offline testing.

**Interface language**: CLI output uses Chinese; code, comments, API paths/params use English.

**PWA**: Service Worker requires HTTPS — won't register on LAN HTTP. All online features work without it. Fonts load from Google Fonts CDN; degrade to system fonts if network is unavailable.
