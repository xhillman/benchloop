from fastapi import APIRouter, Request

from benchloop_api.api.contracts import ApiResponseModel, build_error_responses
from benchloop_api.config import get_app_settings

router = APIRouter(
    tags=["health"],
    responses=build_error_responses(500),
)


class HealthResponse(ApiResponseModel):
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
