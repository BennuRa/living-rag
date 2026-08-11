from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.approval_tasks import (
    router as approval_tasks_router,
)
from app.api.routes.audit_logs import (
    router as audit_logs_router,
)
from app.api.routes.business_actions import (
    router as business_actions_router,
)
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.qa import (
    chat_router,
)
from app.api.routes.qa import (
    router as qa_router,
)
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.review_tasks import (
    router as review_tasks_router,
)
from app.api.routes.runs import (
    router as runs_router,
)
from app.api.routes.users import router as users_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Reserve one lifecycle boundary for database and telemetry setup."""
    yield


settings = get_settings()

app = FastAPI(
    title="Living RAG API",
    version="0.1.0",
    description=(
        "Dynamic knowledge freshness and conflict-governance "
        "agent API."
    ),
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
app.include_router(qa_router)
app.include_router(chat_router)
app.include_router(review_tasks_router)
app.include_router(approval_tasks_router)
app.include_router(business_actions_router)
app.include_router(audit_logs_router)
app.include_router(runs_router)
app.include_router(users_router)
