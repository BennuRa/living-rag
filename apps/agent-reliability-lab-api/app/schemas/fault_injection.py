from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FaultInjectionType(StrEnum):
    EMPTY_RETRIEVAL = "empty_retrieval"
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_ERROR = "tool_error"
    PERMISSION_DENIED = "permission_denied"
    MALFORMED_OUTPUT = "malformed_output"
    STALE_CITATION = "stale_citation"
    UNRESOLVED_CONFLICT = "unresolved_conflict"


class FaultInjectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    fault_type: FaultInjectionType | None = None
    target_node: str | None = Field(default=None, max_length=128)
    target_tool: str | None = Field(default=None, max_length=128)
    message: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)