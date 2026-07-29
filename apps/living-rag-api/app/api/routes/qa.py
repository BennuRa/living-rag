"""HTTP routes for the Living RAG question-answering workflow."""

from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.qa import (
    QuestionAnswerRequest,
    QuestionAnswerResponse,
)
from app.services.embedding_factory import create_embedding_provider
from app.services.llm import MockLLMProvider
from app.services.qa_graph import build_qa_graph
from app.services.qa_persistence import (
    NodeSnapshot,
    save_qa_run,
)


router = APIRouter(
    prefix="/api/qa",
    tags=["question-answering"],
)


@router.post(
    "/answer",
    response_model=QuestionAnswerResponse,
)
def answer_question(
    request: QuestionAnswerRequest,
    db: Session = Depends(get_db),
) -> QuestionAnswerResponse:
    """Answer a question and persist its traceable execution records."""

    trace_id = uuid4()
    embedding_provider = create_embedding_provider()
    llm_provider = MockLLMProvider()

    graph = build_qa_graph(
        llm_provider=llm_provider,
        db=db,
        embedding_provider=embedding_provider,
    )

    initial_state = {
        "question": request.question,
        "user_id": str(request.user_id),
        "trace_id": str(trace_id),
        "limit": request.limit,
    }

    result = dict(initial_state)
    node_snapshots: list[NodeSnapshot] = []

    for sequence_number, update in enumerate(
        graph.stream(
            initial_state,
            stream_mode="updates",
        ),
        start=1,
    ):
        node_name, node_output = next(iter(update.items()))

        result.update(node_output)

        node_snapshots.append(
            NodeSnapshot(
                node_name=node_name,
                sequence_number=sequence_number,
                status="succeeded",
                input_snapshot={},
                output_snapshot=jsonable_encoder(node_output),
                duration_ms=0,
            ),
        )

    save_qa_run(
        db,
        result,
        user_id=request.user_id,
        trace_id=trace_id,
        node_snapshots=node_snapshots,
    )

    return QuestionAnswerResponse(
        trace_id=trace_id,
        answer=result.get(
            "answer",
            "I do not have enough grounded evidence to answer this question.",
        ),
        conditions=result.get(
            "conditions",
            [],
        ),
        citation_valid=result.get(
            "citation_valid",
            False,
        ),
        citations=result.get(
            "citations",
            [],
        ),
        confidence=result.get(
            "confidence",
            0.0,
        ),
        limitations=result.get(
            "limitations",
            [],
        ),
    )