from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchloop_api.ownership.repository import UserOwnedRepository
from benchloop_api.settings.models import UserProviderCredential, UserSettings


class UserSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_user(self, *, user_id: UUID) -> UserSettings | None:
        statement = select(UserSettings).where(UserSettings.user_id == user_id)
        return self._session.scalar(statement)

    def add(self, settings: UserSettings) -> UserSettings:
        self._session.add(settings)
        return settings


class UserProviderCredentialRepository(UserOwnedRepository[UserProviderCredential]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, UserProviderCredential)
        self._session = session

    def list_active(self, *, user_id: UUID) -> Sequence[UserProviderCredential]:
        statement = (
            self._owned_statement(user_id=user_id)
            .where(UserProviderCredential.is_active.is_(True))
            .order_by(
                UserProviderCredential.provider.asc(),
                UserProviderCredential.created_at.asc(),
            )
        )
        return self._session.scalars(statement).all()

    def get_active_owned(
        self,
        *,
        user_id: UUID,
        resource_id: UUID,
    ) -> UserProviderCredential | None:
        statement = self._owned_statement(user_id=user_id).where(
            UserProviderCredential.id == resource_id,
            UserProviderCredential.is_active.is_(True),
        )
        return self._session.scalar(statement)

    def get_active_for_provider(
        self,
        *,
        user_id: UUID,
        provider: str,
    ) -> UserProviderCredential | None:
        statement = self._owned_statement(user_id=user_id).where(
            UserProviderCredential.provider == provider,
            UserProviderCredential.is_active.is_(True),
        )
        return self._session.scalar(statement)
