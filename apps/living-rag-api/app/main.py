from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.retrieval import router as retrieval_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Reserve one lifecycle boundary for database and telemetry setup on Day 2+."""
    yield


settings = get_settings()
app = FastAPI(
    title="Living RAG API",
    version="0.1.0",
    description="Dynamic knowledge freshness and conflict-governance agent API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(retrieval_router)