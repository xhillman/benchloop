from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from fastapi import Request

ValidationStatus = Literal["valid", "invalid"]

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_VALIDATION_TIMEOUT_SECONDS = 10.0
_INVALID_CREDENTIAL_STATUS_CODES = {401, 403}


@dataclass(frozen=True)
class CredentialValidationResult:
    status: ValidationStatus


class UnsupportedCredentialProviderError(Exception):
    def __init__(self, *, provider: str) -> None:
        self.provider = provider
        super().__init__(
            f"Provider '{provider}' is not supported for credential validation."
        )


class ProviderCredentialValidationError(Exception):
    def __init__(self, *, provider: str) -> None:
        self.provider = provider
        super().__init__(
            f"Credential validation could not be completed for provider '{provider}'."
        )


class CredentialValidationAdapter(Protocol):
    provider: str

    async def validate(self, *, api_key: str) -> CredentialValidationResult: ...


class OpenAICredentialValidationAdapter:
    provider = "openai"

    def __init__(
        self,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = DEFAULT_VALIDATION_TIMEOUT_SECONDS,
    ) -> None:
        self._http_transport = http_transport
        self._timeout_seconds = timeout_seconds

    async def validate(self, *, api_key: str) -> CredentialValidationResult:
        return await _run_validation_request(
            provider=self.provider,
            url=OPENAI_MODELS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            http_transport=self._http_transport,
            timeout_seconds=self._timeout_seconds,
        )


class AnthropicCredentialValidationAdapter:
    provider = "anthropic"

    def __init__(
        self,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = DEFAULT_VALIDATION_TIMEOUT_SECONDS,
    ) -> None:
        self._http_transport = http_transport
        self._timeout_seconds = timeout_seconds

    async def validate(self, *, api_key: str) -> CredentialValidationResult:
        return await _run_validation_request(
            provider=self.provider,
            url=ANTHROPIC_MODELS_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
            },
            http_transport=self._http_transport,
            timeout_seconds=self._timeout_seconds,
        )


class ProviderCredentialValidator:
    def __init__(self, *, adapters: list[CredentialValidationAdapter]) -> None:
        self._adapters = {adapter.provider: adapter for adapter in adapters}

    async def validate(
        self,
        *,
        provider: str,
        api_key: str,
    ) -> CredentialValidationResult:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise UnsupportedCredentialProviderError(provider=provider)

        return await adapter.validate(api_key=api_key)


async def _run_validation_request(
    *,
    provider: str,
    url: str,
    headers: dict[str, str],
    http_transport: httpx.AsyncBaseTransport | None,
    timeout_seconds: float,
) -> CredentialValidationResult:
    try:
        async with httpx.AsyncClient(
            transport=http_transport,
            timeout=timeout_seconds,
        ) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise ProviderCredentialValidationError(provider=provider) from exc

    if response.status_code == 200:
        return CredentialValidationResult(status="valid")

    if response.status_code in _INVALID_CREDENTIAL_STATUS_CODES:
        return CredentialValidationResult(status="invalid")

    raise ProviderCredentialValidationError(provider=provider)


def create_provider_credential_validator(
    *,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> ProviderCredentialValidator:
    return ProviderCredentialValidator(
        adapters=[
            OpenAICredentialValidationAdapter(http_transport=http_transport),
            AnthropicCredentialValidationAdapter(http_transport=http_transport),
        ]
    )


def get_provider_credential_validator(request: Request) -> ProviderCredentialValidator:
    return request.app.state.provider_credential_validator
