from typing import Annotated

from fastapi import APIRouter, Depends

from benchloop_api.api.contracts import ApiResponseModel, documented_error_statuses
from benchloop_api.auth.dependencies import require_authenticated_principal
from benchloop_api.auth.models import AuthenticatedPrincipal

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses=documented_error_statuses(include_auth=True),
)


class AuthMeResponse(ApiResponseModel):
    external_user_id: str


@router.get("/me", response_model=AuthMeResponse)
async def read_authenticated_user(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)],
) -> AuthMeResponse:
    return AuthMeResponse(external_user_id=principal.subject)
