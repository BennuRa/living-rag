from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.run_config import RunConfig


def test_run_config_uses_defaults_and_normalizes_workflow_version() -> None:
    config = RunConfig(workflow_version="  0.1.0  ")

    assert config.workflow_version == "0.1.0"
    assert config.prompt_version is None
    assert config.timeout_seconds == 30.0
    assert config.model_name is None
    assert config.llm_judge_enabled is False
    assert config.llm_judge_model_name is None
    assert config.max_llm_judge_calls == 0


@pytest.mark.parametrize(
    ("kwargs", "field_name"),
    [
        ({"workflow_version": "   "}, "workflow_version"),
        ({"workflow_version": "0.1.0", "timeout_seconds": 0}, "timeout_seconds"),
        ({"workflow_version": "0.1.0", "timeout_seconds": 301}, "timeout_seconds"),
        ({"workflow_version": "0.1.0", "timeout_second": 30}, "timeout_second"),
    ],
)
def test_run_config_rejects_invalid_input(
    kwargs: dict[str, object],
    field_name: str,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        RunConfig(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("max_concurrency", 0),
        ("max_concurrency", 21),
        ("max_retries", -1),
        ("max_retries", 4),
        ("cost_budget", -0.01),
        ("max_llm_judge_calls", -1),
        ("max_llm_judge_calls", 101),
    ],
)
def test_run_config_rejects_invalid_batch_settings(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        RunConfig(
            workflow_version="0.1.0",
            **{field_name: invalid_value},
        )

    assert field_name in str(exc_info.value)


def test_run_config_uses_safe_batch_defaults() -> None:
    config = RunConfig(
        workflow_version="0.1.0",
    )

    assert config.max_concurrency == 3
    assert config.max_retries == 1
    assert config.cost_budget is None
    assert config.llm_judge_enabled is False
    assert config.max_llm_judge_calls == 0


def test_run_config_accepts_explicit_batch_settings() -> None:
    config = RunConfig(
        workflow_version="0.1.0",
        prompt_version="v1",
        timeout_seconds=60,
        max_concurrency=5,
        max_retries=2,
        cost_budget=1.5,
    )

    assert config.max_concurrency == 5
    assert config.max_retries == 2
    assert config.cost_budget == 1.5


def test_run_config_accepts_enabled_llm_judge_settings() -> None:
    config = RunConfig(
        workflow_version="0.1.0",
        llm_judge_enabled=True,
        llm_judge_model_name="test-judge-model",
        max_llm_judge_calls=3,
    )

    assert config.llm_judge_enabled is True
    assert config.llm_judge_model_name == "test-judge-model"
    assert config.max_llm_judge_calls == 3


@pytest.mark.parametrize(
    ("llm_judge_enabled", "llm_judge_model_name", "max_llm_judge_calls", "message"),
    [
        (
            True,
            None,
            1,
            "llm_judge_model_name",
        ),
        (
            True,
            "test-judge-model",
            0,
            "max_llm_judge_calls",
        ),
        (
            False,
            None,
            1,
            "max_llm_judge_calls",
        ),
    ],
)
def test_run_config_rejects_inconsistent_llm_judge_settings(
    llm_judge_enabled: bool,
    llm_judge_model_name: str | None,
    max_llm_judge_calls: int,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        RunConfig(
            workflow_version="0.1.0",
            llm_judge_enabled=llm_judge_enabled,
            llm_judge_model_name=llm_judge_model_name,
            max_llm_judge_calls=max_llm_judge_calls,
        )
