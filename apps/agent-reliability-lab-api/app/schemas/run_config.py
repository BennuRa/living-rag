from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_version: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ]
    prompt_version: str | None = None
    timeout_seconds: Annotated[float, Field(gt=0, le=300)] = 30.0
    model_name: str | None = None