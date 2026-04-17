from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Celery / Redis
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge"

    # FAISS persistent volume path
    faiss_data_path: str = "/data/faiss"

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Observability
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str | None = None
    service_name: str = "ai-knowledge-worker"


@lru_cache(maxsize=1)
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
