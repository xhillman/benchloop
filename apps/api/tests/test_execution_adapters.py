import asyncio
import json

import httpx
import pytest

from benchloop_api.execution.adapters import (
    AnthropicSingleShotAdapter,
    OpenAISingleShotAdapter,
    ProviderExecutionError,
    ProviderUsage,
    SingleShotProviderRequest,
)


def build_request(*, provider: str, model: str) -> SingleShotProviderRequest:
    return SingleShotProviderRequest(
        provider=provider,
        model=model,
        system_prompt="You are a concise assistant.",
        user_prompt="Answer the user's request.",
        temperature=0.2,
        max_output_tokens=256,
        top_p=0.9,
        api_key="sk-test-secret",
    )


def test_openai_adapter_normalizes_chat_completion_response() -> None:
    captured_headers: dict[str, str] = {}
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers, captured_body
        captured_headers = dict(request.headers)
        captured_body = json.loads(request.content.decode("utf-8"))
        assert request.method == "POST"
        assert request.url == httpx.URL("https://api.openai.com/v1/chat/completions")
        return httpx.Response(
            200,
            json={
                "model": "gpt-4.1-mini-2025-04-14",
                "choices": [
                    {
                        "message": {
                            "content": "Refund approved. The duplicate charge will be reversed.",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 111,
                    "completion_tokens": 29,
                    "total_tokens": 140,
                },
            },
        )

    adapter = OpenAISingleShotAdapter(http_transport=httpx.MockTransport(handler))

    result = asyncio.run(
        adapter.execute(request=build_request(provider="openai", model="gpt-4.1-mini"))
    )

    assert captured_headers["authorization"] == "Bearer sk-test-secret"
    assert captured_body == {
        "model": "gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Answer the user's request."},
        ],
        "temperature": 0.2,
        "max_completion_tokens": 256,
        "top_p": 0.9,
    }
    assert result.provider == "openai"
    assert result.model == "gpt-4.1-mini-2025-04-14"
    assert result.output_text == "Refund approved. The duplicate charge will be reversed."
    assert result.usage == ProviderUsage(
        input_tokens=111,
        output_tokens=29,
        total_tokens=140,
    )
    assert result.latency_ms >= 0


def test_anthropic_adapter_normalizes_messages_response() -> None:
    captured_headers: dict[str, str] = {}
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers, captured_body
        captured_headers = dict(request.headers)
        captured_body = json.loads(request.content.decode("utf-8"))
        assert request.method == "POST"
        assert request.url == httpx.URL("https://api.anthropic.com/v1/messages")
        return httpx.Response(
            200,
            json={
                "model": "claude-3-5-sonnet-20241022",
                "content": [
                    {
                        "type": "text",
                        "text": "Refund approved. Share the reversal timeline with the customer.",
                    }
                ],
                "usage": {
                    "input_tokens": 98,
                    "output_tokens": 37,
                },
            },
        )

    adapter = AnthropicSingleShotAdapter(http_transport=httpx.MockTransport(handler))

    result = asyncio.run(
        adapter.execute(
            request=build_request(
                provider="anthropic",
                model="claude-3-5-sonnet-latest",
            )
        )
    )

    assert captured_headers["x-api-key"] == "sk-test-secret"
    assert captured_headers["anthropic-version"] == "2023-06-01"
    assert captured_body == {
        "model": "claude-3-5-sonnet-latest",
        "system": "You are a concise assistant.",
        "messages": [
            {"role": "user", "content": "Answer the user's request."},
        ],
        "temperature": 0.2,
        "max_tokens": 256,
        "top_p": 0.9,
    }
    assert result.provider == "anthropic"
    assert result.model == "claude-3-5-sonnet-20241022"
    assert result.output_text == "Refund approved. Share the reversal timeline with the customer."
    assert result.usage == ProviderUsage(
        input_tokens=98,
        output_tokens=37,
        total_tokens=135,
    )
    assert result.latency_ms >= 0


def test_openai_adapter_raises_sanitized_error_for_auth_failure() -> None:
    adapter = OpenAISingleShotAdapter(
        http_transport=httpx.MockTransport(
            lambda request: httpx.Response(
                401,
                json={"error": {"message": "Incorrect API key provided: sk-test-secret"}},
            )
        )
    )

    with pytest.raises(
        ProviderExecutionError,
        match="Authentication failed for provider 'openai'",
    ) as exc_info:
        asyncio.run(
            adapter.execute(request=build_request(provider="openai", model="gpt-4.1-mini"))
        )

    assert "sk-test-secret" not in str(exc_info.value)
