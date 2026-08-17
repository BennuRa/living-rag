from __future__ import annotations

import pytest

from app.settings import LLMJudgeSettings


def test_disabled_judge_allows_missing_provider_credentials() -> None:
    settings = LLMJudgeSettings(
        enabled=False,
        api_key=None,
        model_name=None,
        max_calls=3,
    )

    assert settings.enabled is False
    assert settings.api_key is None
    assert settings.model_name is None
    assert settings.max_calls == 3


def test_enabled_judge_requires_complete_provider_configuration() -> None:
    settings = LLMJudgeSettings(
        enabled=True,
        base_url="https://judge.example.test/v1",
        api_key="test-secret",
        model_name="test-judge-model",
        timeout_seconds=15,
        max_calls=2,
    )

    assert settings.enabled is True
    assert settings.base_url == "https://judge.example.test/v1"
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == "test-secret"
    assert settings.model_name == "test-judge-model"
    assert settings.timeout_seconds == 15
    assert settings.max_calls == 2


@pytest.mark.parametrize(
    ("api_key", "model_name", "max_calls", "error_message"),
    [
        (
            None,
            "test-judge-model",
            1,
            "LLM_JUDGE_API_KEY",
        ),
        (
            "test-secret",
            None,
            1,
            "LLM_JUDGE_MODEL_NAME",
        ),
        (
            "test-secret",
            "test-judge-model",
            0,
            "LLM_JUDGE_MAX_CALLS",
        ),
    ],
)
def test_enabled_judge_rejects_incomplete_configuration(
    api_key: str | None,
    model_name: str | None,
    max_calls: int,
    error_message: str,
) -> None:
    with pytest.raises(ValueError, match=error_message):
        LLMJudgeSettings(
            enabled=True,
            api_key=api_key,
            model_name=model_name,
            max_calls=max_calls,
        )
