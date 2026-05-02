"""Core configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Core ──
    APP_ENV: str = "development"
    LOG_LEVEL: str = "DEBUG"

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://edge:edge@localhost:5432/edgebackend"
    DATABASE_POOL_SIZE: int = 20

    # ── Qdrant ──
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # ── vLLM ──
    VLLM_ENABLED: bool = True
    VLLM_BASE_URL: str = "http://vllm:8000/v1"
    VLLM_API_KEY: Optional[str] = None
    VLLM_MODEL: str = "Qwen/Qwen3.5-9B-Instruct"
    VLLM_MAX_TOKENS: int = 8192

    # ── Ollama ──
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://ollama:11434/v1"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    OLLAMA_MAX_TOKENS: int = 8192

    # ── LLM Provider Selection ──
    # "auto" = detect which backend is available (vllm first, then ollama)
    # "vllm" | "ollama" = force a specific provider
    DEFAULT_LLM_PROVIDER: str = "auto"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ──
    SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Upload ──
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 104_857_600  # 100 MB

    # ── Embeddings ──
    EMBEDDINGS_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV.lower() == "development"


settings = Settings()
