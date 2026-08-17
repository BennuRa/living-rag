from __future__ import annotations

from typing import Any

import httpx

from app.services.llm_judge_client import LLMJudgeClientError


class OpenAICompatibleJudgeClient:
    """Call an OpenAI-compatible Chat Completions API for LLM Judge output.

    The client owns no network session. Its caller must provide an
    httpx.AsyncClient so application code controls connection lifetime,
    timeout policy, and test transports.
    """

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        normalized_base_url = base_url.strip().rstrip("/")

        if not normalized_base_url:
            raise ValueError("base_url must be a non-empty URL.")

        if not api_key.strip():
            raise ValueError("api_key must be non-empty.")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0.")

        self._http_client = http_client
        self._base_url = normalized_base_url
        self._api_key = api_key.strip()
        self._timeout_seconds = timeout_seconds

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
    ) -> str:
        """Return structured Judge content from Chat Completions.

        Provider and transport failures are translated to
        LLMJudgeClientError so LLMJudgeService can record them as failed
        Judge reports without swallowing unrelated programming errors.
        """

        if not model_name.strip():
            raise LLMJudgeClientError(
                "Judge model_name must be a non-empty string.",
            )

        request_payload = {
            "model": model_name,
            "temperature": 0,
            "response_format": {
                "type": "json_object",
            },
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        try:
            response = await self._http_client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()

            return self._extract_content(payload)
        except httpx.HTTPError as exc:
            raise LLMJudgeClientError(
                f"OpenAI-compatible Judge request failed: {exc}",
            ) from exc
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise LLMJudgeClientError(
                f"OpenAI-compatible Judge response is invalid: {exc}",
            ) from exc

    @staticmethod
    def _extract_content(payload: Any) -> str:
        if not isinstance(payload, dict):
            raise TypeError("Judge response must be a JSON object.")

        choices = payload["choices"]

        if not isinstance(choices, list) or not choices:
            raise ValueError(
                "Judge response must contain at least one choice.",
            )

        first_choice = choices[0]

        if not isinstance(first_choice, dict):
            raise TypeError("Judge response choice must be an object.")

        message = first_choice["message"]

        if not isinstance(message, dict):
            raise TypeError("Judge response message must be an object.")

        content = message["content"]

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "Judge response message.content must be a non-empty string.",
            )

        return content.strip()
