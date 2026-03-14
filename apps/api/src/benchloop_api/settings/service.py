from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.ownership.service import UserOwnedResourceNotFoundError
from benchloop_api.settings.encryption import EncryptionService
from benchloop_api.settings.models import UserProviderCredential, UserSettings
from benchloop_api.settings.validation import ProviderCredentialValidator
from benchloop_api.settings.repository import (
    UserProviderCredentialRepository,
    UserSettingsRepository,
)


class ActiveCredentialAlreadyExistsError(Exception):
    def __init__(self, *, provider: str) -> None:
        self.provider = provider
        super().__init__(f"An active credential already exists for provider '{provider}'.")


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


class UserProviderCredentialService:
    def __init__(
        self,
        session: Session,
        encryption_service: EncryptionService,
    ) -> None:
        self._session = session
        self._encryption_service = encryption_service
        self._repository = UserProviderCredentialRepository(session)

    def list(self, *, user_id: UUID) -> Sequence[UserProviderCredential]:
        return self._repository.list_active(user_id=user_id)

    def create(
        self,
        *,
        user_id: UUID,
        provider: str,
        api_key: str,
        key_label: str | None,
    ) -> UserProviderCredential:
        existing_credential = self._repository.get_active_for_provider(
            user_id=user_id,
            provider=provider,
        )
        if existing_credential is not None:
            raise ActiveCredentialAlreadyExistsError(provider=provider)

        credential = self._repository.add(
            UserProviderCredential(
                user_id=user_id,
                provider=provider,
                encrypted_api_key=self._encryption_service.encrypt(api_key),
                key_label=key_label,
            )
        )
        self._session.flush()
        self._session.refresh(credential)
        return credential

    def replace(
        self,
        *,
        user_id: UUID,
        credential_id: UUID,
        api_key: str,
        key_label: str | None,
    ) -> UserProviderCredential:
        credential = self._get_active_owned_or_raise(
            user_id=user_id,
            credential_id=credential_id,
        )
        credential.encrypted_api_key = self._encryption_service.encrypt(api_key)
        credential.key_label = key_label
        credential.validation_status = "not_validated"
        credential.last_validated_at = None

        self._session.flush()
        self._session.refresh(credential)
        return credential

    def delete(self, *, user_id: UUID, credential_id: UUID) -> None:
        credential = self._get_active_owned_or_raise(
            user_id=user_id,
            credential_id=credential_id,
        )
        credential.is_active = False
        self._session.flush()

    async def validate(
        self,
        *,
        user_id: UUID,
        credential_id: UUID,
        validator: ProviderCredentialValidator,
    ) -> UserProviderCredential:
        credential = self._get_active_owned_or_raise(
            user_id=user_id,
            credential_id=credential_id,
        )
        api_key = self._encryption_service.decrypt(credential.encrypted_api_key)
        validation_result = await validator.validate(
            provider=credential.provider,
            api_key=api_key,
        )
        credential.validation_status = validation_result.status
        credential.last_validated_at = datetime.now(tz=UTC)

        self._session.flush()
        self._session.refresh(credential)
        return credential

    def _get_active_owned_or_raise(
        self,
        *,
        user_id: UUID,
        credential_id: UUID,
    ) -> UserProviderCredential:
        credential = self._repository.get_active_owned(
            user_id=user_id,
            resource_id=credential_id,
        )
        if credential is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Credential",
                resource_id=credential_id,
                user_id=user_id,
            )
        return credential


def mask_api_key(api_key: str) -> str:
    suffix = api_key[-4:]
    return f"{'*' * 8}{suffix}"
