"""Shared Agent trace schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentNodeTrace(BaseModel):
    """Serializable trace for one Agent node."""

    model_config = ConfigDict(extra="forbid")

    node_name: str = Field(min_length=1, max_length=128)
    sequence_number: int = Field(gt=0)
    status: str = Field(min_length=1, max_length=32)
    duration_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = None


class ToolCallTrace(BaseModel):
    """Serializable trace for one tool call."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=128)
    status: str = Field(min_length=1, max_length=32)
    duration_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = None


class AgentTrace(BaseModel):
    """Serializable summary of one complete Agent execution."""

    model_config = ConfigDict(extra="forbid")

    trace_id: UUID
    agent_run_id: UUID
    status: str = Field(min_length=1, max_length=32)
    intent: str | None = None
    workflow_version: str = Field(min_length=1, max_length=64)
    model_name: str | None = None
    prompt_version: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    nodes: list[AgentNodeTrace] = Field(default_factory=list)
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None