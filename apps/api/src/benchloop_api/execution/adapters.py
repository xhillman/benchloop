from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

import httpx
from fastapi import Request

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 60.0
_AUTH_FAILURE_STATUS_CODES = {401, 403}


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class ProviderExecutionResult:
    provider: str
    model: str
    output_text: str
    usage: ProviderUsage
    latency_ms: int
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class SingleShotProviderRequest:
    provider: str
    model: str
    system_prompt: str | None
    user_prompt: str
    temperature: float
    max_output_tokens: int
    top_p: float | None
    api_key: str


class ProviderExecutionError(Exception):
    def __init__(self, *, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(message)


class SingleShotProviderAdapter(Protocol):
    provider: str

    async def execute(
        self,
        *,
        request: SingleShotProviderRequest,
    ) -> ProviderExecutionResult: ...


class OpenAISingleShotAdapter:
    provider = "openai"

    def __init__(
        self,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    ) -> None:
        self._http_transport = http_transport
        self._timeout_seconds = timeout_seconds

    async def execute(
        self,
        *,
        request: SingleShotProviderRequest,
    ) -> ProviderExecutionResult:
        payload: dict[str, object] = {
            "model": request.model,
            "messages": _build_openai_messages(request=request),
            "temperature": request.temperature,
            "max_completion_tokens": request.max_output_tokens,
        }
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        response_json, latency_ms = await _post_json(
            provider=self.provider,
            url=OPENAI_CHAT_COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {request.api_key}"},
            payload=payload,
            http_transport=self._http_transport,
            timeout_seconds=self._timeout_seconds,
        )

        usage = response_json.get("usage")
        usage_payload: dict[str, object] = usage if isinstance(usage, dict) else {}
        return ProviderExecutionResult(
            provider=self.provider,
            model=str(response_json.get("model") or request.model),
            output_text=_extract_openai_output_text(response_json),
            usage=ProviderUsage(
                input_tokens=_coerce_optional_int(usage_payload.get("prompt_tokens")),
                output_tokens=_coerce_optional_int(usage_payload.get("completion_tokens")),
                total_tokens=_coerce_optional_int(usage_payload.get("total_tokens")),
            ),
            latency_ms=latency_ms,
        )


class AnthropicSingleShotAdapter:
    provider = "anthropic"

    def __init__(
        self,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    ) -> None:
        self._http_transport = http_transport
        self._timeout_seconds = timeout_seconds

    async def execute(
        self,
        *,
        request: SingleShotProviderRequest,
    ) -> ProviderExecutionResult:
        payload: dict[str, object] = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.user_prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        if request.system_prompt is not None:
            payload["system"] = request.system_prompt
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        response_json, latency_ms = await _post_json(
            provider=self.provider,
            url=ANTHROPIC_MESSAGES_URL,
            headers={
                "x-api-key": request.api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
            },
            payload=payload,
            http_transport=self._http_transport,
            timeout_seconds=self._timeout_seconds,
        )

        usage = response_json.get("usage")
        usage_payload: dict[str, object] = usage if isinstance(usage, dict) else {}
        input_tokens = _coerce_optional_int(usage_payload.get("input_tokens"))
        output_tokens = _coerce_optional_int(usage_payload.get("output_tokens"))
        total_tokens = None
        if input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        return ProviderExecutionResult(
            provider=self.provider,
            model=str(response_json.get("model") or request.model),
            output_text=_extract_anthropic_output_text(response_json),
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
            latency_ms=latency_ms,
        )


class ProviderAdapterRegistry:
    def __init__(self, *, adapters: list[SingleShotProviderAdapter]) -> None:
        self._adapters = {adapter.provider: adapter for adapter in adapters}

    def get(self, *, provider: str) -> SingleShotProviderAdapter | None:
        return self._adapters.get(provider)


async def _post_json(
    *,
    provider: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    http_transport: httpx.AsyncBaseTransport | None,
    timeout_seconds: float,
) -> tuple[dict[str, object], int]:
    started = perf_counter()
    try:
        async with httpx.AsyncClient(
            transport=http_transport,
            timeout=timeout_seconds,
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise ProviderExecutionError(
            provider=provider,
            message=f"Provider '{provider}' request could not be completed.",
        ) from exc

    latency_ms = int((perf_counter() - started) * 1000)
    if response.status_code in _AUTH_FAILURE_STATUS_CODES:
        raise ProviderExecutionError(
            provider=provider,
            message=f"Authentication failed for provider '{provider}'.",
        )
    if response.status_code >= 400:
        raise ProviderExecutionError(
            provider=provider,
            message=f"Provider '{provider}' request failed with status {response.status_code}.",
        )

    try:
        payload_json = response.json()
    except ValueError as exc:
        raise ProviderExecutionError(
            provider=provider,
            message=f"Provider '{provider}' returned an invalid JSON response.",
        ) from exc

    if not isinstance(payload_json, dict):
        raise ProviderExecutionError(
            provider=provider,
            message=f"Provider '{provider}' returned an unexpected response payload.",
        )

    return payload_json, latency_ms


def _build_openai_messages(*, request: SingleShotProviderRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt is not None:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.user_prompt})
    return messages


def _extract_openai_output_text(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderExecutionError(
            provider="openai",
            message="Provider 'openai' returned no completion choices.",
        )

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    text = _normalize_content_text(content)
    if text is None:
        raise ProviderExecutionError(
            provider="openai",
            message="Provider 'openai' returned no output text.",
        )
    return text


def _extract_anthropic_output_text(payload: dict[str, object]) -> str:
    content = payload.get("content")
    text = _normalize_content_text(content)
    if text is None:
        raise ProviderExecutionError(
            provider="anthropic",
            message="Provider 'anthropic' returned no output text.",
        )
    return text


def _normalize_content_text(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if item.get("type") == "text" and isinstance(text, str):
                text_parts.append(text)
        normalized = "".join(text_parts).strip()
        return normalized or None
    return None


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def create_provider_adapter_registry(
    *,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> ProviderAdapterRegistry:
    return ProviderAdapterRegistry(
        adapters=[
            OpenAISingleShotAdapter(http_transport=http_transport),
            AnthropicSingleShotAdapter(http_transport=http_transport),
        ]
    )


def get_provider_adapter_registry(request: Request) -> ProviderAdapterRegistry:
    return request.app.state.provider_adapter_registry
