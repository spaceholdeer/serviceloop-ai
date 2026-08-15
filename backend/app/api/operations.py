"""运营后台知识闭环 API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.customer_service import CustomerServiceDependencies
from app.agents.knowledge_operations import KnowledgeOperationsAgent
from app.api.customer import get_customer_service_dependencies
from app.db import get_session
from app.schemas.operations import (
    KnowledgeAgentRunRequest,
    KnowledgeAgentRunResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentWriteRequest,
    KnowledgeDraftPublishRequest,
    KnowledgeDraftResponse,
    KnowledgeDraftUpdateRequest,
    KnowledgeGapResponse,
    KnowledgePublishResult,
    KnowledgeVersionResponse,
    OperationsOverviewResponse,
)
from app.services.knowledge_operations import (
    KnowledgeOperationsService,
    KnowledgeRecordConflictError,
    KnowledgeRecordNotFoundError,
)

router = APIRouter(prefix="/api/operations", tags=["operations"])


def get_knowledge_operations_service(
    session: Annotated[Session, Depends(get_session)],
    dependencies: Annotated[
        CustomerServiceDependencies, Depends(get_customer_service_dependencies)
    ],
) -> KnowledgeOperationsService:
    return KnowledgeOperationsService(session=session, knowledge=dependencies.knowledge)


def get_knowledge_operations_agent(
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> KnowledgeOperationsAgent:
    return KnowledgeOperationsAgent(service=service)


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc) or "knowledge record not found")


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/overview", response_model=OperationsOverviewResponse)
def operations_overview(
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> OperationsOverviewResponse:
    return OperationsOverviewResponse.model_validate(service.overview())


@router.get("/knowledge-gaps", response_model=list[KnowledgeGapResponse])
def list_knowledge_gap_candidates(
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
    gap_status: Annotated[str | None, Query(alias="status")] = "pending",
) -> list[KnowledgeGapResponse]:
    return [KnowledgeGapResponse.model_validate(item) for item in service.list_gaps(status=gap_status)]


@router.post("/knowledge-gaps/{gap_id}/dismiss", response_model=KnowledgeGapResponse)
def dismiss_knowledge_gap(
    gap_id: str,
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> KnowledgeGapResponse:
    try:
        return KnowledgeGapResponse.model_validate(service.dismiss_gap(gap_id))
    except KnowledgeRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/knowledge-agent/run",
    response_model=KnowledgeAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_knowledge_operations_agent(
    payload: KnowledgeAgentRunRequest,
    agent: Annotated[KnowledgeOperationsAgent, Depends(get_knowledge_operations_agent)],
) -> KnowledgeAgentRunResponse:
    return KnowledgeAgentRunResponse.model_validate(
        agent.run(gap_ids=payload.gap_ids or None, operator_id=payload.operator_id)
    )


@router.get("/knowledge-drafts", response_model=list[KnowledgeDraftResponse])
def list_knowledge_drafts(
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
    draft_status: Annotated[str | None, Query(alias="status")] = None,
) -> list[KnowledgeDraftResponse]:
    return [
        KnowledgeDraftResponse.model_validate(item)
        for item in service.list_drafts(status=draft_status)
    ]


@router.get("/knowledge-drafts/{draft_id}", response_model=KnowledgeDraftResponse)
def get_knowledge_draft(
    draft_id: str,
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> KnowledgeDraftResponse:
    try:
        return KnowledgeDraftResponse.model_validate(service.get_draft(draft_id))
    except KnowledgeRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch("/knowledge-drafts/{draft_id}", response_model=KnowledgeDraftResponse)
def update_knowledge_draft(
    draft_id: str,
    payload: KnowledgeDraftUpdateRequest,
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> KnowledgeDraftResponse:
    try:
        result = service.update_draft(
            draft_id=draft_id, title=payload.title, content=payload.content
        )
    except KnowledgeRecordNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeRecordConflictError as exc:
        raise _conflict(exc) from exc
    return KnowledgeDraftResponse.model_validate(result)


@router.post("/knowledge-drafts/{draft_id}/publish", response_model=KnowledgePublishResult)
def publish_knowledge_draft(
    draft_id: str,
    payload: KnowledgeDraftPublishRequest,
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> KnowledgePublishResult:
    try:
        result = service.publish_draft(
            draft_id=draft_id,
            operator_id=payload.operator_id,
            document_id=payload.document_id,
        )
    except KnowledgeRecordNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeRecordConflictError as exc:
        raise _conflict(exc) from exc
    return KnowledgePublishResult.model_validate(result)


@router.get("/knowledge-documents", response_model=list[KnowledgeDocumentResponse])
def list_knowledge_documents(
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
    document_status: Annotated[str | None, Query(alias="status")] = None,
) -> list[KnowledgeDocumentResponse]:
    return [
        KnowledgeDocumentResponse.model_validate(item)
        for item in service.list_documents(status=document_status)
    ]


@router.post(
    "/knowledge-documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_document(
    payload: KnowledgeDocumentWriteRequest,
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse.model_validate(
        service.publish_document(
            title=payload.title,
            content=payload.content,
            operator_id=payload.operator_id,
            source=payload.source,
        )
    )


@router.put("/knowledge-documents/{document_id}", response_model=KnowledgeDocumentResponse)
def update_knowledge_document(
    document_id: str,
    payload: KnowledgeDocumentWriteRequest,
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> KnowledgeDocumentResponse:
    try:
        service.get_document(document_id)
    except KnowledgeRecordNotFoundError as exc:
        raise _not_found(exc) from exc
    return KnowledgeDocumentResponse.model_validate(
        service.publish_document(
            document_id=document_id,
            title=payload.title,
            content=payload.content,
            operator_id=payload.operator_id,
            source=payload.source,
        )
    )


@router.get(
    "/knowledge-documents/{document_id}/versions",
    response_model=list[KnowledgeVersionResponse],
)
def list_knowledge_document_versions(
    document_id: str,
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> list[KnowledgeVersionResponse]:
    try:
        versions = service.list_versions(document_id)
    except KnowledgeRecordNotFoundError as exc:
        raise _not_found(exc) from exc
    return [KnowledgeVersionResponse.model_validate(item) for item in versions]


@router.delete("/knowledge-documents/{document_id}", response_model=KnowledgeDocumentResponse)
def archive_knowledge_document(
    document_id: str,
    service: Annotated[KnowledgeOperationsService, Depends(get_knowledge_operations_service)],
) -> KnowledgeDocumentResponse:
    try:
        return KnowledgeDocumentResponse.model_validate(service.archive_document(document_id))
    except KnowledgeRecordNotFoundError as exc:
        raise _not_found(exc) from exc
