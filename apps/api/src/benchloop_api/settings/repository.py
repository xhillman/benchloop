from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchloop_api.settings.models import UserSettings


class UserSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_user(self, *, user_id: UUID) -> UserSettings | None:
        statement = select(UserSettings).where(UserSettings.user_id == user_id)
        return self._session.scalar(statement)

    def add(self, settings: UserSettings) -> UserSettings:
        self._session.add(settings)
        return settings
