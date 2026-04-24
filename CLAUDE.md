# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rhizome-thinking is a personal knowledge base system where nodes are connected by tags and semantic relationships. It follows a three-stage implementation plan:

- **Stage 1**: CLI pipe validation (Markdown storage, LLM processing)
- **Stage 2**: Semantic retrieval with ChromaDB + cross-device access via FastAPI + PWA
- **Stage 3**: Graphical epistemic map view

Currently in Stage 1→2 transition.

## Architecture

```
src/rhizome/
├── core/
│   ├── models.py      # Node, Link, Source, Processed data classes
│   ├── node_store.py  # Markdown file storage
│   └── llm_processor.py  # MiniMax API processing
├── api/
│   └── routes/        # FastAPI endpoints (nodes, query, links, stats)
├── retrieval/
│   ├── vector_store.py   # ChromaDB + SiliconFlow embeddings
│   └── query_engine.py   # Semantic search with modifiers
├── cli.py             # Click-based CLI (rhz command)
└── config.py          # Settings via pydantic-settings
```

## Running Commands

```bash
# CLI usage
python -m rhizome --help                    # Show all commands
python -m rhizome add "note content"       # Add a node
python -m rhizome add -f note.txt          # Add from file
python -m rhizome list --tag needs_thinking # List with filter
python -m rhizome show <node-id>           # Show node details
python -m rhizome stats                     # Knowledge base stats
python -m rhizome query "search text"      # Semantic query (Stage 2)
python -m rhizome serve --reload           # Start FastAPI server

# Run tests
pytest tests/ -v

# Install dependencies
pip install -e ".[stage1]"     # Stage 1 only
pip install -e ".[stage2]"     # Includes FastAPI, ChromaDB
```

## Key Design Decisions

**Data Model**: Nodes are stored as Markdown files with YAML frontmatter. Each node has:
- `proposition`: LLM-distilled core statement
- `open_questions`: Questions explicitly raised by user
- `tags`: One or more of `definitive`, `inferred`, `vague`, `needs_thinking`, `cross-domain`
- `links`: Node connections with `support`, `contradict`, `extend`, `source`, `analogy` types

**Tag types** map to Chinese in CLI output: `needs_thinking`→需要思考, `vague`→模糊, etc.

**Interface Language**: CLI output uses Chinese; code/comments remain in English. API endpoints use English paths/params.

**API Keys**: Configuration via `.env` file. MiniMax for LLM processing, SiliconFlow for embeddings. Set `USE_MOCK_EMBEDDING=true` for offline testing.