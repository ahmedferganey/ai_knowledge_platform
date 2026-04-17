from fastapi import FastAPI

from app.routers.health import router as health_router
from core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router, prefix=app_settings.api_v1_prefix)

    return app


app = create_app()
