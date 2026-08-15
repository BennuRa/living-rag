from __future__ import annotations

import asyncio
import sys

import httpx

from app.adapters.living_rag import LivingRAGAdapter
from app.schemas.run_config import RunConfig


async def main(trace_id: str) -> None:
    config = RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=30,
    )

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
    ) as client:
        adapter = LivingRAGAdapter(client)
        trace_detail = await adapter.get_trace(
            trace_id,
            timeout_seconds=config.timeout_seconds,
        )

    agent_run = trace_detail.get("agent_run", {})
    if not isinstance(agent_run, dict):
        raise TypeError("Living RAG trace agent_run must be an object")

    messages = trace_detail.get("messages", [])
    if not isinstance(messages, list):
        raise TypeError("Living RAG trace messages must be a list")

    print(f"trace_id: {trace_detail.get('trace_id')}")
    print(f"run_status: {agent_run.get('status')}")
    print(f"intent: {agent_run.get('intent')}")
    print(f"workflow_version: {agent_run.get('workflow_version')}")
    print(f"node_count: {len(trace_detail.get('nodes', []))}")
    print(f"tool_call_count: {len(trace_detail.get('tool_calls', []))}")
    print(f"message_count: {len(messages)}")
    print(f"approval_task_count: {len(trace_detail.get('approval_tasks', []))}")
    print(f"audit_log_count: {len(trace_detail.get('audit_logs', []))}")

    print("messages:")
    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")
        print(f"  [{role}] {content}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/get_living_rag_trace.py <trace_id>")

    asyncio.run(main(sys.argv[1]))
