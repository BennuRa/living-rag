from __future__ import annotations

import asyncio

import httpx

from app.adapters.living_rag import LivingRAGAdapter
from app.schemas.run_config import RunConfig
from app.services.task_dataset_loader import load_shared_agent_task_cases


async def main() -> None:
    tasks = load_shared_agent_task_cases()

    task = next(
        (item for item in tasks if item.case_id == "eligibility-001"),
        None,
    )
    if task is None:
        raise RuntimeError("Shared task eligibility-001 was not found")

    config = RunConfig(
        workflow_version="0.1.0",
        prompt_version="day18-real-integration",
        timeout_seconds=30,
    )

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
    ) as client:
        adapter = LivingRAGAdapter(client)
        result = await adapter.run(task, config)

    print(f"case_id: {task.case_id}")
    print(f"route: {task.expected_route}")
    print(f"status: {result.status}")
    print(f"final_answer: {result.final_answer}")
    print(f"trace_id: {result.trace_id}")
    print(f"latency_ms: {result.latency_ms:.2f}")
    print(f"error_message: {result.error_message}")
    print(f"citation_count: {len(result.citations)}")


if __name__ == "__main__":
    asyncio.run(main())