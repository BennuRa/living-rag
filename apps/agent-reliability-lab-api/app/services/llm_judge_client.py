from __future__ import annotations

from typing import Protocol


class LLMJudgeClientError(Exception):
    """A provider-level failure that the Judge service may safely record."""


class LLMJudgeClient(Protocol):
    """Provider-neutral interface for one structured LLM Judge call.

    Concrete implementations may call an OpenAI-compatible API, a local
    model, or a deterministic fake client used by tests. Provider and
    transport failures must be raised as LLMJudgeClientError.
    """

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
    ) -> str:
        """Return the raw text response from the Judge model.

        Raises:
            LLMJudgeClientError: When the provider or transport fails.
        """
