from fastapi import APIRouter, Response, status

from app.schemas.health import HealthResponse, ReadinessResponse
from services.health import HealthService, ReadinessService

router = APIRouter(tags=["health"])

_health_service = HealthService()
_readiness_service = ReadinessService()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Kubernetes liveness probe. Returns 200 while the process is alive.",
)
async def health() -> HealthResponse:
    return _health_service.get_health()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description=(
        "Kubernetes readiness probe. Checks all critical dependencies. "
        "Returns 200 when ready to serve traffic, 503 when not ready."
    ),
)
async def ready(response: Response) -> ReadinessResponse:
    result = await _readiness_service.check_readiness()
    if result.status == "not_ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
