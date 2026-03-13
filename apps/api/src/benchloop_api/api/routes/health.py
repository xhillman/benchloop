from fastapi import APIRouter, Request
from pydantic import BaseModel

from benchloop_api.config import get_app_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def read_health(request: Request) -> HealthResponse:
    settings = get_app_settings(request.app)
    return HealthResponse(
        status="ok",
        service="benchloop-api",
        environment=settings.environment,
    )
