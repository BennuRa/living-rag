from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx
from pydantic import ValidationError

from app.adapters.target_agent import TargetAgentAdapter
from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.citation import Citation
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.run_config import RunConfig


class LivingRAGAdapter(TargetAgentAdapter):
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get_trace(
        self,
        trace_id: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        if not trace_id.strip():
            raise ValueError("trace_id must not be blank")

        response = await self._client.get(
            f"/runs/{trace_id}",
            timeout=timeout_seconds,
        )
        response.raise_for_status()

        trace_detail = response.json()
        if not isinstance(trace_detail, dict):
            raise TypeError(
                "Living RAG /runs/{trace_id} response must be an object"
            )

        return trace_detail

    async def _resolve_user_id(
        self,
        external_id: str,
        timeout_seconds: float,
    ) -> str:
        response = await self._client.get(
            "/api/users",
            timeout=timeout_seconds,
        )
        response.raise_for_status()

        users = response.json()
        if not isinstance(users, list):
            raise TypeError(
                "Living RAG /api/users response must be a list"
            )

        for user in users:
            if not isinstance(user, dict):
                continue

            if user.get("external_id") != external_id:
                continue

            user_id = user.get("id")
            if isinstance(user_id, str) and user_id:
                return user_id

            raise TypeError(
                "Living RAG /api/business-actions response "
                "must be an object"
            )

        raise ValueError(
            f"Living RAG user not found for external_id={external_id!r}"
        )

    async def run(
        self,
        task: AgentTaskCase,
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> AgentRunResult:
        started_at = perf_counter()

        def elapsed_ms() -> float:
            return max(0.0, (perf_counter() - started_at) * 1000)

        try:
            if fault is not None and fault.enabled:
                return AgentRunResult(
                    status="failed",
                    latency_ms=elapsed_ms(),
                    error_message=(
                        "Fault injection is not supported by "
                        "LivingRAGAdapter yet"
                    ),
                )

            external_id = task.context.get("user_external_id")
            if not isinstance(external_id, str) or not external_id.strip():
                return AgentRunResult(
                    status="failed",
                    latency_ms=elapsed_ms(),
                    error_message=(
                        "Agent task context requires a non-empty "
                        "user_external_id"
                    ),
                )

            if task.expected_route not in {
                "policy_qa",
                "refund_eligibility",
            }:
                return AgentRunResult(
                    status="failed",
                    latency_ms=elapsed_ms(),
                    error_message=(
                        f"Unsupported Living RAG route: "
                        f"{task.expected_route!r}"
                    ),
                )

            user_id = await self._resolve_user_id(
                external_id=external_id,
                timeout_seconds=config.timeout_seconds,
            )

            if task.expected_route == "policy_qa":
                response = await self._client.post(
                    "/api/chat",
                    json={
                        "user_id": user_id,
                        "question": task.user_input,
                    },
                    timeout=config.timeout_seconds,
                )
                response.raise_for_status()

                raw_response = response.json()
                if not isinstance(raw_response, dict):
                    raise ValueError(
                        "Living RAG /api/chat response must be an object"
                    )

                citation_data = raw_response.get("citations", [])
                if not isinstance(citation_data, list):
                    raise ValueError(
                        "Living RAG /api/chat citations must be a list"
                    )

                citations = [
                    Citation.model_validate(item)
                    for item in citation_data
                ]

                return AgentRunResult(
                    status="succeeded",
                    final_answer=raw_response.get("answer"),
                    citations=citations,
                    trace_id=raw_response.get("trace_id"),
                    latency_ms=elapsed_ms(),
                    raw_response=raw_response,
                )

            payload: dict[str, Any] = {
                "user_id": user_id,
                "question": task.user_input,
            }
            as_of = task.context.get("as_of")
            if isinstance(as_of, str) and as_of.strip():
                payload["as_of"] = as_of

            response = await self._client.post(
                "/api/business-actions",
                json=payload,
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()

            raw_response = response.json()
            if not isinstance(raw_response, dict):
                raise TypeError(
                    "Living RAG /api/business-actions response "
                    "must be an object"
                )

            return AgentRunResult(
                status="succeeded",
                final_answer=raw_response.get("message"),
                citations=[],
                trace_id=raw_response.get("trace_id"),
                latency_ms=elapsed_ms(),
                raw_response=raw_response,
            )

        except httpx.TimeoutException:
            return AgentRunResult(
                status="timed_out",
                latency_ms=elapsed_ms(),
                error_message="Living RAG request timed out",
            )

        except httpx.HTTPError as exc:
            return AgentRunResult(
                status="failed",
                latency_ms=elapsed_ms(),
                error_message=f"Living RAG HTTP request failed: {exc}",
            )

        except (ValidationError, ValueError, TypeError) as exc:
            return AgentRunResult(
                status="failed",
                latency_ms=elapsed_ms(),
                error_message=f"Living RAG adapter failed: {exc}",
            )