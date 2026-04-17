from fastapi import APIRouter

from app.schemas.health import HealthResponse
from services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthService().get_health()
