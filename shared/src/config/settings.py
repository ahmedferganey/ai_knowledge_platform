"""
Comprehensive Pydantic Settings for the RAG platform.
All services import from this module; service-specific extensions inherit Settings.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    app_name: str = Field(default="AI Knowledge Platform", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    service_name: str = Field(default="rag", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ── Database ───────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://rag:rag@localhost:5432/rag",
        alias="DATABASE_URL",
    )

    # ── Cache / Broker ─────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_BROKER_URL",
    )

    # ── Vector store ───────────────────────────────────────────────────────
    faiss_data_path: str = Field(default="/data/faiss", alias="FAISS_DATA_PATH")

    # ── LLM providers ──────────────────────────────────────────────────────
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    # ── External identity provider ─────────────────────────────────────────
    auth_jwks_url: str | None = Field(default=None, alias="AUTH_JWKS_URL")
    auth_token_issuer: str | None = Field(default=None, alias="AUTH_TOKEN_ISSUER")

    # ── Ingestion ──────────────────────────────────────────────────────────
    embedding_model_name: str = Field(
        default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL_NAME"
    )
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE", ge=64, le=4096)
    chunk_overlap: int = Field(default=64, alias="CHUNK_OVERLAP", ge=0, le=512)
    max_file_size_bytes: int = Field(
        default=10 * 1024 * 1024, alias="MAX_FILE_SIZE_BYTES", ge=1
    )

    # ── Rate limiting ──────────────────────────────────────────────────────
    query_rate_limit_per_minute: int = Field(
        default=20, alias="QUERY_RATE_LIMIT_PER_MINUTE", ge=1
    )
    upload_rate_limit_per_minute: int = Field(
        default=10, alias="UPLOAD_RATE_LIMIT_PER_MINUTE", ge=1
    )

    # ── Response cache ─────────────────────────────────────────────────────
    cache_ttl_seconds: int = Field(
        default=3600, alias="CACHE_TTL_SECONDS", ge=0
    )

    # ── Observability ──────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        allowed = {"openai", "claude"}
        if v not in allowed:
            raise ValueError(f"llm_provider must be one of {allowed}, got {v!r}")
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_less_than_chunk_size(cls, v: int, info: object) -> int:
        # Accessed via info.data in Pydantic v2
        data = getattr(info, "data", {})
        chunk_size = data.get("chunk_size", 512)
        if v >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
