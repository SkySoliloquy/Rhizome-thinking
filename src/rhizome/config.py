"""Configuration management for Rhizome Thinking."""

import secrets
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # MiniMax API Configuration (for LLM processing)
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimaxi.chat/v1"
    minimax_model: str = "minimax-text-01"
    minimax_embedding_model: str = "embedding-01"

    # SiliconFlow Embedding API Configuration
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_embedding_model: str = "BAAI/bge-large-zh-v1.5"

    # Use mock embedding when API is unavailable or for testing
    use_mock_embedding: bool = False

    # Application Settings
    environment: Literal["development", "production", "testing"] = "development"
    debug: bool = False
    secret_key: str = ""

    # Storage Paths
    storage_dir: Path = Path("./storage")

    # ChromaDB
    chroma_persist_dir: Path = Path("./storage/chroma")
    
    @property
    def nodes_dir(self) -> Path:
        """Directory for markdown node files."""
        return self.storage_dir / "nodes"
    
    @property
    def metadata_dir(self) -> Path:
        """Directory for metadata files."""
        return self.storage_dir / "metadata"
    
    @property
    def nodes_index_path(self) -> Path:
        """Path to nodes index file."""
        return self.metadata_dir / "nodes_index.json"
    
    def ensure_directories(self) -> None:
        """Ensure all storage directories exist."""
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)

    def model_post_init(self, _context) -> None:
        if not self.secret_key:
            self.secret_key = secrets.token_urlsafe(32)


# Global settings instance
settings = Settings()
