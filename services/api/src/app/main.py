from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.routers.health import router as health_router
from core.config import Settings, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup → yield → shutdown."""
    settings: Settings = get_settings()
    app.state.settings = settings
    # Future phases wire DB engine, Redis pool, FAISS index here.
    yield
    # Cleanup resources on shutdown (engines disposed in later phases).


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description="Production-grade AI Knowledge Assistant Platform (RAG System)",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.include_router(health_router, prefix=app_settings.api_v1_prefix)

    return app


app = create_app()
