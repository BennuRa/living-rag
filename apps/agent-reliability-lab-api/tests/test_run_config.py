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