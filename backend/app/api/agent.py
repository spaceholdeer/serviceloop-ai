"""人工客服工作台 API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.agent import (
    AcceptHandoffRequest,
    AgentReplyRequest,
    HandoffDetailResponse,
    HandoffSummaryResponse,
    ResolveHandoffRequest,
)
from app.schemas.customer import MessageResponse
from app.services.human_support import (
    HandoffConflictError,
    HandoffNotFoundError,
    HumanSupportService,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def get_human_support_service(
    session: Annotated[Session, Depends(get_session)],
) -> HumanSupportService:
    return HumanSupportService(session)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="handoff not found")


def _conflict(exc: HandoffConflictError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/handoffs", response_model=list[HandoffSummaryResponse])
def list_handoffs(
    service: Annotated[HumanSupportService, Depends(get_human_support_service)],
    status: Annotated[list[str] | None, Query()] = None,
) -> list[HandoffSummaryResponse]:
    return [HandoffSummaryResponse.model_validate(item) for item in service.list_handoffs(status)]


@router.get("/handoffs/{handoff_id}", response_model=HandoffDetailResponse)
def get_handoff(
    handoff_id: str,
    service: Annotated[HumanSupportService, Depends(get_human_support_service)],
) -> HandoffDetailResponse:
    try:
        return HandoffDetailResponse.model_validate(service.get_handoff(handoff_id))
    except HandoffNotFoundError as exc:
        raise _not_found() from exc


@router.post("/handoffs/{handoff_id}/accept", response_model=HandoffDetailResponse)
def accept_handoff(
    handoff_id: str,
    payload: AcceptHandoffRequest,
    service: Annotated[HumanSupportService, Depends(get_human_support_service)],
) -> HandoffDetailResponse:
    try:
        return HandoffDetailResponse.model_validate(
            service.accept(handoff_id=handoff_id, agent_id=payload.agent_id)
        )
    except HandoffNotFoundError as exc:
        raise _not_found() from exc
    except HandoffConflictError as exc:
        raise _conflict(exc) from exc


@router.post("/handoffs/{handoff_id}/messages", response_model=MessageResponse)
def reply_to_customer(
    handoff_id: str,
    payload: AgentReplyRequest,
    service: Annotated[HumanSupportService, Depends(get_human_support_service)],
) -> MessageResponse:
    try:
        message = service.reply(
            handoff_id=handoff_id,
            agent_id=payload.agent_id,
            content=payload.content,
        )
        return MessageResponse.model_validate(message)
    except HandoffNotFoundError as exc:
        raise _not_found() from exc
    except HandoffConflictError as exc:
        raise _conflict(exc) from exc


@router.post("/handoffs/{handoff_id}/resolve", response_model=HandoffDetailResponse)
def resolve_handoff(
    handoff_id: str,
    payload: ResolveHandoffRequest,
    service: Annotated[HumanSupportService, Depends(get_human_support_service)],
) -> HandoffDetailResponse:
    try:
        return HandoffDetailResponse.model_validate(
            service.resolve(
                handoff_id=handoff_id,
                agent_id=payload.agent_id,
                resolution_code=payload.resolution_code,
                action_taken=payload.action_taken,
                reply_to_customer=payload.reply_to_customer,
                internal_notes=payload.internal_notes,
            )
        )
    except HandoffNotFoundError as exc:
        raise _not_found() from exc
    except HandoffConflictError as exc:
        raise _conflict(exc) from exc
