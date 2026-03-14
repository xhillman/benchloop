from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.settings.models import UserSettings
from benchloop_api.settings.repository import UserSettingsRepository


class UserSettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = UserSettingsRepository(session)

    def read(self, *, user_id: UUID) -> UserSettings | None:
        return self._repository.get_for_user(user_id=user_id)

    def update(
        self,
        *,
        user_id: UUID,
        default_provider: str | None,
        default_model: str | None,
        timezone: str | None,
    ) -> UserSettings:
        settings = self._repository.get_for_user(user_id=user_id)
        if settings is None:
            settings = self._repository.add(
                UserSettings(
                    user_id=user_id,
                    default_provider=default_provider,
                    default_model=default_model,
                    timezone=timezone,
                )
            )
        else:
            settings.default_provider = default_provider
            settings.default_model = default_model
            settings.timezone = timezone

        self._session.flush()
        self._session.refresh(settings)
        return settings
