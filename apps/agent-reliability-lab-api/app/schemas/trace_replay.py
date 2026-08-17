from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TraceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=32)
    content: str = ""
    created_at: datetime | None = None


class TraceNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_name: str = Field(min_length=1, max_length=128)
    status: str | None = Field(default=None, max_length=32)
    latency_ms: float | None = Field(default=None, ge=0)
    input_summary: str | None = None
    output_summary: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TraceToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=128)
    status: str | None = Field(default=None, max_length=32)
    latency_ms: float | None = Field(default=None, ge=0)
    input_summary: str | None = None
    output_summary: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TraceApprovalTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_task_id: str = Field(min_length=1, max_length=128)
    status: str | None = Field(default=None, max_length=32)
    action: str | None = Field(default=None, max_length=128)
    reason: str | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None


class TraceAuditLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=128)
    status: str | None = Field(default=None, max_length=32)
    actor: str | None = Field(default=None, max_length=128)
    detail: str | None = None
    created_at: datetime | None = None


class TraceReplay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(min_length=1, max_length=128)
    run_status: str = Field(min_length=1, max_length=32)
    intent: str | None = Field(default=None, max_length=128)
    workflow_version: str | None = Field(default=None, max_length=64)
    action: str | None = Field(default=None, max_length=128)
    approval_task_id: str | None = Field(default=None, max_length=128)
    refund_request_id: str | None = Field(default=None, max_length=128)
    retrieval_status: str | None = Field(default=None, max_length=64)
    conflict_status: str | None = Field(default=None, max_length=64)
    final_answer: str | None = None

    messages: list[TraceMessage] = Field(default_factory=list)
    nodes: list[TraceNode] = Field(default_factory=list)
    tool_calls: list[TraceToolCall] = Field(default_factory=list)
    approval_tasks: list[TraceApprovalTask] = Field(default_factory=list)
    audit_logs: list[TraceAuditLog] = Field(default_factory=list)

    citations: list[dict[str, Any]] = Field(default_factory=list)
