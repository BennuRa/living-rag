from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import DocumentSourceType
from app.schemas.document import (
    DocumentUploadForm,
    DocumentUploadResponse,
    DocumentVersionListItem,
)
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_parsing import parse_uploaded_content


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
)
async def upload_document(
    title: Annotated[str, Form(...)],
    domain: Annotated[str, Form(...)],
    policy_key: Annotated[str, Form(...)],
    source_type: Annotated[DocumentSourceType, Form(...)],
    version_number: Annotated[int, Form(...)],
    effective_at: Annotated[datetime, Form(...)],
    expires_at: Annotated[datetime | None, Form()] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    try:
        form = DocumentUploadForm(
            title=title,
            domain=domain,
            policy_key=policy_key,
            source_type=source_type,
            version_number=version_number,
            effective_at=effective_at,
            expires_at=expires_at,
        )

        content_bytes = await file.read()

        parsed_content = parse_uploaded_content(
            file.filename or "",
            content_bytes,
        )

        service = DocumentIngestionService(db)

        document = service.get_or_create_document(
            title=form.title,
            domain=form.domain,
            policy_key=form.policy_key,
        )

        version = service.ingest_content(
            document=document,
            content=parsed_content,
            requested_version_number=form.version_number,
            source_type=form.source_type,
            effective_at=form.effective_at,
            expires_at=form.expires_at,
            original_filename=file.filename,
            content_type=file.content_type,
        )

        db.commit()

    except ValueError as error:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except Exception:
        db.rollback()
        raise

    return DocumentUploadResponse(
        document_id=document.id,
        document_version_id=version.id,
        policy_key=document.policy_key,
        version_number=version.version_number,
        content_hash=version.content_hash,
        source_type=version.source_type,
        effective_at=version.effective_at,
        expires_at=version.expires_at,
        original_filename=version.original_filename,
        content_type=version.content_type,
        chunk_count=len(version.chunks),
    )


@router.get(
    "/{policy_key}/versions",
    response_model=list[DocumentVersionListItem],
)
async def list_document_versions(
    policy_key: str,
    db: Session = Depends(get_db),
) -> list[DocumentVersionListItem]:
    service = DocumentIngestionService(db)
    versions = service.list_document_versions(policy_key)
    responses: list[DocumentVersionListItem] = []

    for version in versions:
        response = DocumentVersionListItem(
            document_id=version.document_id,
            document_version_id=version.id,
            policy_key=policy_key,
            version_number=version.version_number,
            content_hash=version.content_hash,
            source_type=version.source_type,
            governance_status=version.governance_status,
            effective_at=version.effective_at,
            expires_at=version.expires_at,
            original_filename=version.original_filename,
            content_type=version.content_type,
            chunk_count=len(version.chunks),
        )
        responses.append(response)

    return responses
