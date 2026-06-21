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
    VLLM_ENABLED: bool = False
    VLLM_BASE_URL: str = "http://vllm:8000/v1"
    VLLM_API_KEY: Optional[str] = None
    VLLM_MODEL: str = "Qwen/Qwen3.5-9B-Instruct"
    VLLM_MAX_TOKENS: int = 8192

    # ── Ollama ──
    OLLAMA_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen3.5:4b"
    OLLAMA_MAX_TOKENS: int = 8192
    OLLAMA_NUM_CTX: int = 65536

    # ── LLM Provider Selection ──
    # "auto" = detect which backend is available (vllm first, then ollama)
    # "vllm" | "ollama" = force a specific provider
    DEFAULT_LLM_PROVIDER: str = "ollama"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ──
    SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    EVENT_INGEST_API_KEY: str = "change-me-event-ingest-key"

    # ── OAuth ──
    OAUTH_REDIRECT_URL: str = "http://localhost/api/v1/integrations/oauth/callback"
    GMAIL_CLIENT_ID: str | None = None
    GMAIL_CLIENT_SECRET: str | None = None

    # ── Credential Encryption ──
    CREDENTIAL_ENCRYPTION_KEY: str | None = None  # If not set, falls back to SECRET_KEY
    CREDENTIAL_ENCRYPTION_KEY_PREVIOUS: str | None = None  # For key rotation

    # ── Frontend ──
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # ── CORS ──
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── MinIO / S3 Object Storage ──
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "documents"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"

    # ── Upload limits ──
    MAX_UPLOAD_SIZE: int = 104_857_600  # 100 MB

    # ── Embeddings ──
    EMBEDDINGS_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    SPARSE_EMBEDDINGS_MODEL: str = "Qdrant/bm25"

    # ── RAG Pipeline ──
    HYBRID_SEARCH_ENABLED: bool = True
    RAG_PREFETCH_LIMIT: int = 50
    RAG_RERANK_TOP_K: int = 5
    RAG_MIN_RELEVANCE_SCORE: float = 0.01

    # ── Reranker ──
    RERANKER_ENABLED: bool = False
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # ── Contextual Chunking ──
    CONTEXTUAL_CHUNKING_ENABLED: bool = False

    # ── Query Enhancement ──
    QUERY_ENHANCEMENT_ENABLED: bool = False

    # ── Reactive Pipeline ──
    REACTIVE_NOTIFICATION_EMAIL: str = "stefano.andres2004@gmail.com"

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV.lower() == "development"


settings = Settings()
