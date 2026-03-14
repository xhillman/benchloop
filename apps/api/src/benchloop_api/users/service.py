from typing import Any

from sqlalchemy.orm import Session

from benchloop_api.auth.models import AuthenticatedPrincipal
from benchloop_api.users.models import User
from benchloop_api.users.repository import UserRepository


class UserSyncService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)

    def sync_authenticated_principal(self, principal: AuthenticatedPrincipal) -> User:
        user = self._users.get_by_clerk_user_id(principal.subject)
        email = _extract_email_from_claims(principal.claims)

        if user is None:
            user = self._users.add(
                User(
                    clerk_user_id=principal.subject,
                    email=email,
                )
            )
        elif email is not None and user.email != email:
            user.email = email

        self._session.flush()
        self._session.refresh(user)
        return user


def _extract_email_from_claims(claims: dict[str, Any]) -> str | None:
    for key in ("email", "email_address"):
        value = claims.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized

    return None
