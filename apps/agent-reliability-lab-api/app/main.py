from fastapi import FastAPI

from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.health import router as health_router
from app.api.routes.traces import router as traces_router

app = FastAPI(
    title="Agent Reliability Lab API",
    version="0.1.0",
    description="Evaluation and reliability platform for Living RAG.",
)

app.include_router(health_router)
app.include_router(evaluations_router)
app.include_router(traces_router)