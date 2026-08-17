from __future__ import annotations

import json

import httpx
import pytest

from app.services.llm_judge_client import LLMJudgeClientError
from app.services.openai_compatible_judge_client import (
    OpenAICompatibleJudgeClient,
)


def make_success_response(content: str) -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                },
            },
        ],
    }


@pytest.mark.asyncio
async def test_client_sends_openai_compatible_judge_request() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request

        captured_request = request

        return httpx.Response(
            status_code=200,
            json=make_success_response(
                '{"overall_score": 80, "passed": true}',
            ),
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAICompatibleJudgeClient(
            http_client=http_client,
            base_url="https://judge.example.test/v1/",
            api_key="test-api-key",
            timeout_seconds=5,
        )

        response = await client.complete(
            system_prompt="You are a strict Agent evaluator.",
            user_prompt="Evaluate this generic Agent result.",
            model_name="test-judge-model",
        )

    assert response == '{"overall_score": 80, "passed": true}'
    assert captured_request is not None
    assert captured_request.method == "POST"
    assert str(captured_request.url) == ("https://judge.example.test/v1/chat/completions")
    assert captured_request.headers["Authorization"] == "Bearer test-api-key"

    request_payload = json.loads(captured_request.content)

    assert request_payload["model"] == "test-judge-model"
    assert request_payload["temperature"] == 0
    assert request_payload["response_format"] == {
        "type": "json_object",
    }
    assert request_payload["messages"] == [
        {
            "role": "system",
            "content": "You are a strict Agent evaluator.",
        },
        {
            "role": "user",
            "content": "Evaluate this generic Agent result.",
        },
    ]


@pytest.mark.asyncio
async def test_client_translates_http_failure_to_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=503,
            json={
                "error": {
                    "message": "Judge provider is unavailable.",
                },
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAICompatibleJudgeClient(
            http_client=http_client,
            base_url="https://judge.example.test/v1",
            api_key="test-api-key",
        )

        with pytest.raises(LLMJudgeClientError, match="request failed"):
            await client.complete(
                system_prompt="System prompt",
                user_prompt="User prompt",
                model_name="test-judge-model",
            )


@pytest.mark.asyncio
async def test_client_rejects_response_without_non_empty_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json=make_success_response(""),
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAICompatibleJudgeClient(
            http_client=http_client,
            base_url="https://judge.example.test/v1",
            api_key="test-api-key",
        )

        with pytest.raises(
            LLMJudgeClientError,
            match="response is invalid",
        ):
            await client.complete(
                system_prompt="System prompt",
                user_prompt="User prompt",
                model_name="test-judge-model",
            )


@pytest.mark.parametrize(
    ("base_url", "api_key", "timeout_seconds", "error_message"),
    [
        ("", "test-api-key", 30, "base_url"),
        ("https://judge.example.test/v1", "", 30, "api_key"),
        ("https://judge.example.test/v1", "test-api-key", 0, "timeout_seconds"),
    ],
)
def test_client_rejects_invalid_constructor_configuration(
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    error_message: str,
) -> None:
    async_client = httpx.AsyncClient()

    try:
        with pytest.raises(ValueError, match=error_message):
            OpenAICompatibleJudgeClient(
                http_client=async_client,
                base_url=base_url,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
            )
    finally:
        import asyncio

        asyncio.run(async_client.aclose())
