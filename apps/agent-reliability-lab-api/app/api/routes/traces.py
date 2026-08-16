from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException

from app.adapters.living_rag import LivingRAGAdapter
from app.schemas.trace_replay import TraceReplay
from app.services.trace_replay_service import TraceReplayService

LIVING_RAG_BASE_URL = os.getenv(
    "LIVING_RAG_BASE_URL",
    "http://127.0.0.1:8000",
)
TRACE_TIMEOUT_SECONDS = 30.0

router = APIRouter(
    prefix="/api/traces",
    tags=["traces"],
)

trace_replay_service = TraceReplayService()


@router.get(
    "/{trace_id}",
    response_model=TraceReplay,
    summary="Read and normalize a Living RAG trace",
)
async def read_trace(trace_id: str) -> TraceReplay:
    normalized_trace_id = trace_id.strip()
    if not normalized_trace_id:
        raise HTTPException(
            status_code=400,
            detail="trace_id must not be blank",
        )

    try:
        async with httpx.AsyncClient(
            base_url=LIVING_RAG_BASE_URL,
        ) as client:
            adapter = LivingRAGAdapter(client)
            raw_trace = await adapter.get_trace(
                normalized_trace_id,
                timeout_seconds=TRACE_TIMEOUT_SECONDS,
            )

        return trace_replay_service.build_replay(raw_trace)

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Living RAG returned an HTTP error while reading the trace: "
                f"{exc}"
            ),
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not reach Living RAG while reading the trace: "
                f"{exc}"
            ),
        ) from exc

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Living RAG trace payload is invalid: {exc}",
        ) from exc