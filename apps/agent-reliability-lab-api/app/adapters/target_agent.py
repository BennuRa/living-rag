from __future__ import annotations

from typing import Protocol

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.run_config import RunConfig


class TargetAgentAdapter(Protocol):
    async def run(
        self,
        task: AgentTaskCase,
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> AgentRunResult:
        ...