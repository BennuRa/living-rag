import pytest
from pydantic import ValidationError

from app.schemas.run_config import RunConfig


def test_run_config_uses_defaults_and_normalizes_workflow_version() -> None:
    config = RunConfig(workflow_version="  0.1.0  ")

    assert config.workflow_version == "0.1.0"
    assert config.prompt_version is None
    assert config.timeout_seconds == 30.0
    assert config.model_name is None


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