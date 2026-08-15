"""用户端 Customer Service Agent API。"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from openai import OpenAIError
from sqlalchemy.orm import Session

from app.agents.customer_service import CustomerServiceAgent, CustomerServiceDependencies
from app.db import get_session
from app.db.session import create_session_factory
from app.repositories import KnowledgeOperationsRepository
from app.schemas.customer import (
    ConversationCreateRequest,
    ConversationResponse,
    CustomerChatRequest,
    CustomerChatResponse,
    CustomerHumanMessageRequest,
    MessageResponse,
)
from app.services.customer_chat import (
    ConversationNotFoundError,
    ConversationUnavailableError,
    CustomerChatService,
)
from app.services.knowledge import KnowledgeService

router = APIRouter(prefix="/api/customer", tags=["customer"])


@lru_cache(maxsize=1)
def get_runtime_knowledge_service() -> KnowledgeService:
    """从 MySQL 恢复知识，并让客服端与运营端共享同一份运行时索引。"""

    service = KnowledgeService()
    try:
        with create_session_factory()() as session:
            documents = KnowledgeOperationsRepository(session).list_published_payloads()
            service.replace_all(documents)
    except Exception as exc:
        raise RuntimeError(f"知识索引恢复失败：{exc}") from exc
    return service


@lru_cache(maxsize=1)
def get_customer_service_dependencies() -> CustomerServiceDependencies:
    return CustomerServiceDependencies(knowledge=get_runtime_knowledge_service())


@lru_cache(maxsize=1)
def get_customer_service_agent() -> CustomerServiceAgent:
    try:
        return CustomerServiceAgent(dependencies=get_customer_service_dependencies())
    except (OpenAIError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def get_customer_chat_service(
    session: Annotated[Session, Depends(get_session)],
    agent: Annotated[CustomerServiceAgent, Depends(get_customer_service_agent)],
) -> CustomerChatService:
    return CustomerChatService(session=session, agent=agent)


def get_customer_conversation_service(
    session: Annotated[Session, Depends(get_session)],
) -> CustomerChatService:
    return CustomerChatService(session=session)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="conversation not found")


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreateRequest,
    service: Annotated[CustomerChatService, Depends(get_customer_conversation_service)],
) -> ConversationResponse:
    return ConversationResponse.model_validate(
        service.create_conversation(customer_id=payload.customer_id, subject=payload.subject)
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    customer_id: Annotated[str, Query(min_length=1, max_length=64)],
    service: Annotated[CustomerChatService, Depends(get_customer_conversation_service)],
) -> ConversationResponse:
    try:
        conversation = service.get_conversation(
            conversation_id=conversation_id,
            customer_id=customer_id,
        )
    except ConversationNotFoundError as exc:
        raise _not_found() from exc
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(
    customer_id: Annotated[str, Query(min_length=1, max_length=64)],
    service: Annotated[CustomerChatService, Depends(get_customer_conversation_service)],
) -> list[ConversationResponse]:
    return [
        ConversationResponse.model_validate(conversation)
        for conversation in service.list_conversations(customer_id=customer_id)
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def list_conversation_messages(
    conversation_id: str,
    customer_id: Annotated[str, Query(min_length=1, max_length=64)],
    service: Annotated[CustomerChatService, Depends(get_customer_conversation_service)],
) -> list[MessageResponse]:
    try:
        messages = service.list_messages(
            conversation_id=conversation_id,
            customer_id=customer_id,
        )
    except ConversationNotFoundError as exc:
        raise _not_found() from exc
    return [MessageResponse.model_validate(message) for message in messages]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
)
def send_message_to_human(
    conversation_id: str,
    payload: CustomerHumanMessageRequest,
    service: Annotated[CustomerChatService, Depends(get_customer_conversation_service)],
) -> MessageResponse:
    try:
        message = service.send_human_message(
            conversation_id=conversation_id,
            customer_id=payload.customer_id,
            message=payload.content,
        )
    except ConversationNotFoundError as exc:
        raise _not_found() from exc
    except ConversationUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"conversation is not handled by a human agent: {exc}",
        ) from exc
    return MessageResponse.model_validate(message)


@router.post("/chat", response_model=CustomerChatResponse)
def customer_chat(
    payload: CustomerChatRequest,
    service: Annotated[CustomerChatService, Depends(get_customer_chat_service)],
) -> CustomerChatResponse:
    try:
        result = service.chat(
            conversation_id=payload.conversation_id,
            customer_id=payload.customer_id,
            message=payload.message,
        )
    except ConversationNotFoundError as exc:
        raise _not_found() from exc
    except ConversationUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"conversation is not active: {exc}",
        ) from exc
    except (OpenAIError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return CustomerChatResponse(
        conversation_id=result["conversation_id"],
        conversation_status=result["conversation_status"],
        customer_message_id=result["customer_message_id"],
        assistant_message_id=result["assistant_message_id"],
        answer=result["final_answer"],
        handoff_required=result["handoff_required"],
        handoff_reason=result.get("handoff_reason"),
        handoff=result.get("handoff"),
        tool_events=result.get("tool_events", []),
        original_query=result.get("original_query"),
        rewritten_query=result.get("rewritten_query"),
        rewrite_count=result.get("rewrite_count", 0),
        retrieval_attempts=result.get("retrieval_attempts", []),
        customer_intent=result.get("customer_intent"),
        evidence_decision=result.get("evidence_decision"),
        knowledge_gap_assessment=result.get("knowledge_gap_assessment"),
        knowledge_gap_candidate=result.get("knowledge_gap_candidate"),
    )
