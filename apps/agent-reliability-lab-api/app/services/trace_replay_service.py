from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.schemas.trace_replay import (
    TraceApprovalTask,
    TraceAuditLog,
    TraceMessage,
    TraceNode,
    TraceReplay,
    TraceToolCall,
)


class TraceReplayService:
    """Translate a Living RAG trace payload into the stable Lab replay schema."""

    def build_replay(self, raw_trace: Mapping[str, Any]) -> TraceReplay:
        if not isinstance(raw_trace, Mapping):
            raise TypeError("raw Living RAG trace must be an object")

        trace_id = self._required_string(raw_trace.get("trace_id"), "trace_id")

        agent_run = raw_trace.get("agent_run", {})
        if agent_run is None:
            agent_run = {}
        if not isinstance(agent_run, Mapping):
            raise TypeError("Living RAG trace agent_run must be an object")

        run_status = self._optional_string(
            raw_trace.get("run_status"),
            agent_run.get("status"),
        ) or "unknown"

        intent = self._optional_string(
            raw_trace.get("intent"),
            agent_run.get("intent"),
        )

        workflow_version = self._optional_string(
            raw_trace.get("workflow_version"),
            agent_run.get("workflow_version"),
        )

        messages = self._build_messages(raw_trace.get("messages", []))
        final_answer = self._resolve_final_answer(
            raw_trace,
            agent_run,
            messages,
        )

        try:
            return TraceReplay(
                trace_id=trace_id,
                run_status=run_status,
                intent=intent,
                workflow_version=workflow_version,
                final_answer=final_answer,
                messages=messages,
                nodes=self._build_nodes(raw_trace.get("nodes", [])),
                tool_calls=self._build_tool_calls(
                    raw_trace.get("tool_calls", []),
                ),
                approval_tasks=self._build_approval_tasks(
                    raw_trace.get("approval_tasks", []),
                ),
                audit_logs=self._build_audit_logs(
                    raw_trace.get("audit_logs", []),
                ),
                citations=self._build_citations(
                    raw_trace.get("citations", []),
                ),
            )
        except ValidationError as exc:
            raise ValueError(f"Invalid normalized TraceReplay: {exc}") from exc

    def _build_messages(self, raw_messages: Any) -> list[TraceMessage]:
        items = self._list_or_empty(raw_messages, "messages")
        messages: list[TraceMessage] = []

        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise TypeError(
                    f"Living RAG trace messages[{index}] must be an object",
                )

            role = self._required_string(
                item.get("role"),
                f"messages[{index}].role",
            )
            content = self._string_value(item.get("content"), default="")

            messages.append(
                TraceMessage(
                    role=role,
                    content=content,
                    created_at=self._datetime_value(
                        item.get("created_at"),
                    ),
                ),
            )

        return messages

    def _build_nodes(self, raw_nodes: Any) -> list[TraceNode]:
        items = self._list_or_empty(raw_nodes, "nodes")
        nodes: list[TraceNode] = []

        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise TypeError(
                    f"Living RAG trace nodes[{index}] must be an object",
                )

            node_name = self._required_string(
                item.get("node_name", item.get("name")),
                f"nodes[{index}].node_name",
            )

            nodes.append(
                TraceNode(
                    node_name=node_name,
                    status=self._optional_string(item.get("status")),
                    latency_ms=self._float_value(item.get("latency_ms")),
                    input_summary=self._summary_value(
                        item.get("input_summary", item.get("input")),
                    ),
                    output_summary=self._summary_value(
                        item.get("output_summary", item.get("output")),
                    ),
                    started_at=self._datetime_value(
                        item.get("started_at"),
                    ),
                    completed_at=self._datetime_value(
                        item.get("completed_at"),
                    ),
                ),
            )

        return nodes

    def _build_tool_calls(self, raw_tool_calls: Any) -> list[TraceToolCall]:
        items = self._list_or_empty(raw_tool_calls, "tool_calls")
        tool_calls: list[TraceToolCall] = []

        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise TypeError(
                    f"Living RAG trace tool_calls[{index}] must be an object",
                )

            tool_name = self._required_string(
                item.get("tool_name", item.get("name")),
                f"tool_calls[{index}].tool_name",
            )

            tool_calls.append(
                TraceToolCall(
                    tool_name=tool_name,
                    status=self._optional_string(item.get("status")),
                    latency_ms=self._float_value(item.get("latency_ms")),
                    input_summary=self._summary_value(
                        item.get("input_summary", item.get("input")),
                    ),
                    output_summary=self._summary_value(
                        item.get("output_summary", item.get("output")),
                    ),
                    error_message=self._optional_string(
                        item.get("error_message"),
                    ),
                    started_at=self._datetime_value(
                        item.get("started_at"),
                    ),
                    completed_at=self._datetime_value(
                        item.get("completed_at"),
                    ),
                ),
            )

        return tool_calls

    def _build_approval_tasks(
        self,
        raw_approval_tasks: Any,
    ) -> list[TraceApprovalTask]:
        items = self._list_or_empty(
            raw_approval_tasks,
            "approval_tasks",
        )
        approval_tasks: list[TraceApprovalTask] = []

        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise TypeError(
                    "Living RAG trace "
                    f"approval_tasks[{index}] must be an object",
                )

            approval_task_id = self._required_string(
                item.get(
                    "approval_task_id",
                    item.get("id"),
                ),
                f"approval_tasks[{index}].approval_task_id",
            )

            approval_tasks.append(
                TraceApprovalTask(
                    approval_task_id=approval_task_id,
                    status=self._optional_string(item.get("status")),
                    action=self._optional_string(item.get("action")),
                    reason=self._optional_string(item.get("reason")),
                    created_at=self._datetime_value(
                        item.get("created_at"),
                    ),
                    decided_at=self._datetime_value(
                        item.get("decided_at"),
                    ),
                ),
            )

        return approval_tasks

    def _build_audit_logs(self, raw_audit_logs: Any) -> list[TraceAuditLog]:
        items = self._list_or_empty(raw_audit_logs, "audit_logs")
        audit_logs: list[TraceAuditLog] = []

        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise TypeError(
                    f"Living RAG trace audit_logs[{index}] must be an object",
                )

            action = self._required_string(
                item.get("action"),
                f"audit_logs[{index}].action",
            )

            audit_logs.append(
                TraceAuditLog(
                    action=action,
                    status=self._optional_string(item.get("status")),
                    actor=self._optional_string(item.get("actor")),
                    detail=self._summary_value(
                        item.get("detail"),
                    ),
                    created_at=self._datetime_value(
                        item.get("created_at"),
                    ),
                ),
            )

        return audit_logs

    def _build_citations(self, raw_citations: Any) -> list[dict[str, Any]]:
        items = self._list_or_empty(raw_citations, "citations")
        citations: list[dict[str, Any]] = []

        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise TypeError(
                    f"Living RAG trace citations[{index}] must be an object",
                )

            citations.append(dict(item))

        return citations

    def _resolve_final_answer(
        self,
        raw_trace: Mapping[str, Any],
        agent_run: Mapping[str, Any],
        messages: list[TraceMessage],
    ) -> str | None:
        direct_answer = self._optional_string(
            raw_trace.get("final_answer"),
            agent_run.get("final_answer"),
            agent_run.get("answer"),
        )
        if direct_answer is not None:
            return direct_answer

        for message in reversed(messages):
            if message.role == "assistant" and message.content.strip():
                return message.content

        return None

    @staticmethod
    def _list_or_empty(value: Any, field_name: str) -> list[Any]:
        if value is None:
            return []

        if not isinstance(value, list):
            raise TypeError(
                f"Living RAG trace {field_name} must be a list",
            )

        return value

    @staticmethod
    def _required_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Living RAG trace {field_name} must be a non-empty string",
            )

        return value.strip()

    @staticmethod
    def _optional_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()

        return None

    @staticmethod
    def _string_value(value: Any, default: str = "") -> str:
        if value is None:
            return default

        if isinstance(value, str):
            return value

        return str(value)

    @classmethod
    def _summary_value(cls, value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, str):
            return value

        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _float_value(value: Any) -> float | None:
        if value is None:
            return None

        if isinstance(value, bool):
            raise TypeError("Trace latency must be a number")

        if isinstance(value, (int, float)):
            return float(value)

        raise TypeError("Trace latency must be a number")

    @staticmethod
    def _datetime_value(value: Any) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid Trace datetime value: {value!r}",
                ) from exc
        raise TypeError("Trace datetime must be an ISO string or datetime")