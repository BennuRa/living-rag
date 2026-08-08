"""Pydantic schemas for complete Living RAG run details."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_node_run import AgentNodeRunStatus
from app.models.agent_run import AgentRunStatus
from app.models.chat_message import (
    ChatMessageRole,
    ChatMessageStatus,
)
from app.models.tool_call import ToolCallStatus
from app.schemas.approval_task import ApprovalTaskResponse
from app.schemas.audit_log import AuditLogResponse


class AgentRunDetail(BaseModel):
    """Detailed response model for one complete Agent execution."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )

    id: UUID
    thread_id: UUID
    message_id: UUID | None = None
    trace_id: UUID
    status: AgentRunStatus
    intent: str | None = None
    workflow_version: str = Field(
        min_length=1,
        max_length=64,
    )
    model_name: str | None = None
    prompt_version: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = Field(
        default=None,
        ge=0,
    )
    input_tokens: int | None = Field(
        default=None,
        ge=0,
    )
    output_tokens: int | None = Field(
        default=None,
        ge=0,
    )
    estimated_cost: Decimal | None = Field(
        default=None,
        ge=0,
    )
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, object] = Field(
        default_factory=dict,
        validation_alias="metadata_",
        serialization_alias="metadata",
    )


class AgentNodeRunDetail(BaseModel):
    """Detailed response model for one LangGraph node execution."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )

    id: UUID
    agent_run_id: UUID
    node_name: str = Field(
        min_length=1,
        max_length=128,
    )
    sequence_number: int = Field(
        gt=0,
    )
    status: AgentNodeRunStatus
    input_snapshot: dict[str, object] = Field(
        default_factory=dict,
    )
    output_snapshot: dict[str, object] = Field(
        default_factory=dict,
    )
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = Field(
        default=None,
        ge=0,
    )
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, object] = Field(
        default_factory=dict,
        validation_alias="metadata_",
        serialization_alias="metadata",
    )


class ToolCallDetail(BaseModel):
    """Detailed response model for one Agent tool call."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )

    id: UUID
    agent_run_id: UUID
    node_run_id: UUID | None = None
    tool_name: str = Field(
        min_length=1,
        max_length=128,
    )
    status: ToolCallStatus
    arguments: dict[str, object] = Field(
        default_factory=dict,
    )
    result: dict[str, object] = Field(
        default_factory=dict,
    )
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = Field(
        default=None,
        ge=0,
    )
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, object] = Field(
        default_factory=dict,
        validation_alias="metadata_",
        serialization_alias="metadata",
    )


class ChatMessageDetail(BaseModel):
    """Detailed response model for one conversation message."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )

    id: UUID
    thread_id: UUID
    sequence_number: int = Field(
        gt=0,
    )
    role: ChatMessageRole
    content: str = Field(
        min_length=1,
    )
    status: ChatMessageStatus
    trace_id: UUID | None = None
    citations: list[dict[str, object]] = Field(
        default_factory=list,
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class RunDetailResponse(BaseModel):
    """Complete response model for one Agent run and its Trace records."""

    model_config = ConfigDict(
        extra="forbid",
    )

    trace_id: UUID
    agent_run: AgentRunDetail
    nodes: list[AgentNodeRunDetail] = Field(
        default_factory=list,
    )
    tool_calls: list[ToolCallDetail] = Field(
        default_factory=list,
    )
    messages: list[ChatMessageDetail] = Field(
        default_factory=list,
    )
    approval_tasks: list[ApprovalTaskResponse] = Field(
        default_factory=list,
    )
    audit_logs: list[AuditLogResponse] = Field(
        default_factory=list,
    )