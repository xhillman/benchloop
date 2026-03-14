import asyncio

import httpx
import pytest

from benchloop_api.settings.validation import (
    AnthropicCredentialValidationAdapter,
    OpenAICredentialValidationAdapter,
    ProviderCredentialValidationError,
    ProviderCredentialValidator,
    UnsupportedCredentialProviderError,
)


def test_openai_validation_adapter_marks_credential_valid_on_200_response() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = dict(request.headers)
        assert request.method == "GET"
        assert request.url == httpx.URL("https://api.openai.com/v1/models")
        return httpx.Response(200, json={"data": []})

    adapter = OpenAICredentialValidationAdapter(
        http_transport=httpx.MockTransport(handler)
    )

    result = asyncio.run(adapter.validate(api_key="sk-openai-secret"))

    assert result.status == "valid"
    assert captured_headers["authorization"] == "Bearer sk-openai-secret"


def test_openai_validation_adapter_marks_credential_invalid_on_401_response() -> None:
    adapter = OpenAICredentialValidationAdapter(
        http_transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": {"message": "Unauthorized"}})
        )
    )

    result = asyncio.run(adapter.validate(api_key="sk-openai-invalid"))

    assert result.status == "invalid"


def test_anthropic_validation_adapter_uses_required_headers_and_marks_valid() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = dict(request.headers)
        assert request.method == "GET"
        assert request.url == httpx.URL("https://api.anthropic.com/v1/models")
        return httpx.Response(200, json={"data": []})

    adapter = AnthropicCredentialValidationAdapter(
        http_transport=httpx.MockTransport(handler)
    )

    result = asyncio.run(adapter.validate(api_key="sk-ant-secret"))

    assert result.status == "valid"
    assert captured_headers["x-api-key"] == "sk-ant-secret"
    assert captured_headers["anthropic-version"] == "2023-06-01"


def test_validation_adapter_raises_on_upstream_provider_failure() -> None:
    adapter = AnthropicCredentialValidationAdapter(
        http_transport=httpx.MockTransport(
            lambda request: httpx.Response(500, json={"error": {"message": "boom"}})
        )
    )

    with pytest.raises(
        ProviderCredentialValidationError,
        match="could not be completed for provider 'anthropic'",
    ):
        asyncio.run(adapter.validate(api_key="sk-ant-secret"))


def test_provider_validator_rejects_unsupported_providers() -> None:
    validator = ProviderCredentialValidator(adapters=[])

    with pytest.raises(
        UnsupportedCredentialProviderError,
        match="Provider 'mistral' is not supported",
    ):
        asyncio.run(validator.validate(provider="mistral", api_key="sk-unsupported"))
