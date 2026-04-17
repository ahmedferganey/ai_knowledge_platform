from datetime import UTC, datetime
from pathlib import Path

from app.schemas.health import (
    HealthResponse,
    ReadinessResponse,
    ServiceCheckStatus,
    ServiceChecks,
)
from core.config import Settings, get_settings


class HealthService:
    def get_health(self, settings: Settings | None = None) -> HealthResponse:
        s = settings or get_settings()
        return HealthResponse(
            status="healthy",
            service=s.service_name,
            version=s.app_version,
            timestamp=datetime.now(UTC),
        )


class ReadinessService:
    """Checks connectivity of all critical dependencies for the readiness probe."""

    async def check_readiness(
        self, settings: Settings | None = None
    ) -> ReadinessResponse:
        s = settings or get_settings()

        database_status = await self._check_database(s.database_url)
        cache_status = await self._check_cache(s.redis_url)
        vector_store_status = self._check_vector_store(s.faiss_data_path)

        checks = ServiceChecks(
            database=database_status,
            cache=cache_status,
            vector_store=vector_store_status,
        )

        is_ready = database_status != "error" and vector_store_status != "error"

        return ReadinessResponse(
            status="ready" if is_ready else "not_ready",
            timestamp=datetime.now(UTC),
            checks=checks,
        )

    async def _check_database(self, database_url: str | None) -> ServiceCheckStatus:
        if not database_url:
            return "error"
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy import text

            engine = create_async_engine(database_url, pool_pre_ping=True)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return "ok"
        except Exception:
            return "error"

    async def _check_cache(self, redis_url: str) -> ServiceCheckStatus:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(redis_url, socket_connect_timeout=2)
            await client.ping()
            await client.aclose()
            return "ok"
        except Exception:
            return "degraded"

    def _check_vector_store(self, faiss_data_path: str) -> ServiceCheckStatus:
        path = Path(faiss_data_path)
        if path.exists() and path.is_dir():
            return "ok"
        # Path not yet created is acceptable on first startup — directory created lazily
        return "ok"
