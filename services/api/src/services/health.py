from datetime import UTC, datetime

from app.schemas.health import HealthResponse
from core.config import get_settings


class HealthService:
    def get_health(self) -> HealthResponse:
        settings = get_settings()
        return HealthResponse(
            status="healthy",
            service=settings.service_name,
            version=settings.app_version,
            timestamp=datetime.now(UTC),
        )
