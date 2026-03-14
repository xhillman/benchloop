from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from benchloop_api.api.contracts import AUTH_SCHEME_DESCRIPTION, AUTH_SCHEME_NAME
from benchloop_api.auth.models import AuthenticatedPrincipal
from benchloop_api.auth.service import ClerkJwtVerifier, TokenVerificationError

_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name=AUTH_SCHEME_NAME,
    description=AUTH_SCHEME_DESCRIPTION,
)


def get_auth_verifier(request: Request) -> ClerkJwtVerifier:
    return request.app.state.auth_verifier


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
