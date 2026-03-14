from fastapi import APIRouter

from benchloop_api.api.contracts import ApiResponseModel, documented_error_statuses
from benchloop_api.auth.dependencies import CurrentUser

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses=documented_error_statuses(include_auth=True),
)


class AuthMeResponse(ApiResponseModel):
    external_user_id: str


@router.get("/me", response_model=AuthMeResponse)
async def read_authenticated_user(
    current_user: CurrentUser,
) -> AuthMeResponse:
    return AuthMeResponse(external_user_id=current_user.clerk_user_id)
