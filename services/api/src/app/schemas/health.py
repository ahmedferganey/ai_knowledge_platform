from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ServiceCheckStatus = Literal["ok", "degraded", "error"]


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy"]
    service: str
    version: str
    timestamp: datetime


class ServiceChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database: ServiceCheckStatus
    cache: ServiceCheckStatus
    vector_store: ServiceCheckStatus


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    timestamp: datetime
    checks: ServiceChecks
