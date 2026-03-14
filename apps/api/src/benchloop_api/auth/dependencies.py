from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from benchloop_api.api.contracts import AUTH_SCHEME_DESCRIPTION, AUTH_SCHEME_NAME
from benchloop_api.auth.models import AuthenticatedPrincipal
from benchloop_api.auth.service import ClerkJwtVerifier, TokenVerificationError
from benchloop_api.db.session import get_db_session
from benchloop_api.users.models import User
from benchloop_api.users.service import UserSyncService

_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name=AUTH_SCHEME_NAME,
    description=AUTH_SCHEME_DESCRIPTION,
)


def get_auth_verifier(request: Request) -> ClerkJwtVerifier:
    return request.app.state.auth_verifier


def get_user_sync_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> UserSyncService:
    return UserSyncService(session)


async def require_authenticated_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    verifier = get_auth_verifier(request)
    try:
        return await verifier.verify_token(credentials.credentials)
    except TokenVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def require_current_user(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)],
    user_sync_service: Annotated[UserSyncService, Depends(get_user_sync_service)],
) -> User:
    return user_sync_service.sync_authenticated_principal(principal)


CurrentUser = Annotated[User, Depends(require_current_user)]
