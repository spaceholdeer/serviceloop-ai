"""用户提问到客服回答的应用服务。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import (
    Conversation,
    ConversationStatus,
    Handoff,
    HandoffStatus,
    KnowledgeGap,
    Message,
    MessageRole,
    ToolCall,
    ToolCallStatus,
)
from app.repositories import CustomerConversationRepository


class CustomerAgent(Protocol):
    def invoke(
        self,
        *,
        conversation_id: str,
        customer_id: str,
        message: str,
        history: Sequence[dict[str, str]] = (),
    ) -> dict[str, Any]: ...


class ConversationNotFoundError(LookupError):
    pass


class ConversationUnavailableError(RuntimeError):
    pass


TOOL_SERVICE_NAMES = {
    "search_knowledge": "knowledge",
    "get_order": "order",
    "get_logistics": "logistics",
    "create_ticket": "ticket",
    "request_human_handoff": "human",
}


class CustomerChatService:
    """协调数据库和 Agent；不把持久化职责放进 LangGraph 节点。"""

    def __init__(self, *, session: Session, agent: CustomerAgent | None = None):
        self.session = session
        self.agent = agent
        self.repository = CustomerConversationRepository(session)

    def create_conversation(self, *, customer_id: str, subject: str | None = None) -> Conversation:
        conversation = Conversation(customer_id=customer_id, subject=subject)
        self.repository.add_conversation(conversation)
        self._commit()
        return conversation

    def get_conversation(self, *, conversation_id: str, customer_id: str) -> Conversation:
        conversation = self.repository.get(conversation_id)
        if conversation is None or conversation.customer_id != customer_id:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def list_messages(self, *, conversation_id: str, customer_id: str) -> list[Message]:
        self.get_conversation(conversation_id=conversation_id, customer_id=customer_id)
        return self.repository.list_messages(conversation_id)

    def list_conversations(self, *, customer_id: str) -> list[Conversation]:
        return self.repository.list_for_customer(customer_id)

    def send_human_message(
        self,
        *,
        conversation_id: str,
        customer_id: str,
        message: str,
    ) -> Message:
        """人工接管后保存客户消息，不再调用 Customer Service Agent。"""

        conversation = self.get_conversation(
            conversation_id=conversation_id,
            customer_id=customer_id,
        )
        if conversation.status != ConversationStatus.HUMAN_ACTIVE.value:
            raise ConversationUnavailableError(conversation.status)
        record = Message(
            conversation_id=conversation.id,
            role=MessageRole.CUSTOMER.value,
            source="customer",
            content=message.strip(),
        )
        self.repository.add_message(record)
        conversation.updated_at = utc_now()
        self._commit()
        return record

    def chat(
        self,
        *,
        customer_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        if self.agent is None:
            raise RuntimeError("Customer Service Agent is required for chat")
        conversation = self._load_or_prepare_conversation(
            conversation_id=conversation_id,
            customer_id=customer_id,
            message=message,
        )
        history = [
            {"role": item.role, "content": item.content}
            for item in (
                self.repository.list_messages(conversation.id)
                if conversation_id is not None
                else []
            )
        ]

        # 结束读取事务，避免外部模型调用期间占用数据库事务。
        if conversation_id is not None:
            self.session.commit()

        result = self.agent.invoke(
            conversation_id=conversation.id,
            customer_id=customer_id,
            message=message,
            history=history,
        )
        self._persist_turn(
            conversation=conversation,
            customer_message=message,
            result=result,
        )
        result["conversation_id"] = conversation.id
        result["conversation_status"] = conversation.status
        return result

    def _load_or_prepare_conversation(
        self,
        *,
        conversation_id: str | None,
        customer_id: str,
        message: str,
    ) -> Conversation:
        if conversation_id is None:
            return Conversation(
                id=str(uuid4()),
                customer_id=customer_id,
                subject=message[:100],
            )

        conversation = self.get_conversation(
            conversation_id=conversation_id,
            customer_id=customer_id,
        )
        if conversation.status != ConversationStatus.ACTIVE.value:
            raise ConversationUnavailableError(conversation.status)
        return conversation

    def _persist_turn(
        self,
        *,
        conversation: Conversation,
        customer_message: str,
        result: dict[str, Any],
    ) -> None:
        customer_record = Message(
            conversation_id=conversation.id,
            role=MessageRole.CUSTOMER.value,
            source="customer",
            content=customer_message,
        )
        assistant_record = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT.value,
            source="customer_service_agent",
            content=str(result["final_answer"]),
        )

        if self.repository.get(conversation.id) is None:
            self.repository.add_conversation(conversation)
        self.repository.add_message(customer_record)
        self.repository.add_message(assistant_record)

        for event in result.get("tool_events", []):
            operation = str(event.get("service_name") or "unknown")
            status = str(event.get("status") or ToolCallStatus.FAILED.value)
            tool_call = ToolCall(
                conversation_id=conversation.id,
                message=assistant_record,
                service_name=TOOL_SERVICE_NAMES.get(operation, "unknown"),
                operation=operation,
                input_payload=event.get("input") or {},
                output_payload=event.get("result"),
                status=(
                    ToolCallStatus.SUCCEEDED.value
                    if status == ToolCallStatus.SUCCEEDED.value
                    else ToolCallStatus.FAILED.value
                ),
                error_message=(event.get("result") or {}).get("message")
                if status != ToolCallStatus.SUCCEEDED.value
                else None,
            )
            self.repository.add_tool_call(tool_call)

        if result.get("handoff_required"):
            handoff_data = result.get("handoff") or {}
            self.repository.add_handoff(
                Handoff(
                    id=handoff_data.get("handoff_id") or str(uuid4()),
                    conversation_id=conversation.id,
                    reason_code=str(result.get("handoff_reason") or "agent_requested"),
                    reason_detail=handoff_data.get("reason_detail"),
                    customer_question=customer_message,
                    agent_summary=str(
                        handoff_data.get("agent_summary")
                        or f"Customer Service Agent 转人工：{result.get('handoff_reason')}"
                    ),
                    context_package=handoff_data.get("context_package")
                    or {
                        "tool_events": result.get("tool_events", []),
                        "knowledge_gap_assessment": result.get(
                            "knowledge_gap_assessment"
                        ),
                    },
                    status=HandoffStatus.QUEUED.value,
                )
            )
            conversation.status = ConversationStatus.WAITING_FOR_HUMAN.value

        gap_data = result.get("knowledge_gap_candidate")
        if gap_data:
            self.repository.add_knowledge_gap(
                KnowledgeGap(
                    id=str(gap_data.get("knowledge_gap_id") or uuid4()),
                    conversation_id=conversation.id,
                    question=str(gap_data.get("question") or customer_message),
                    reason=str(gap_data.get("reason") or "knowledge_insufficient"),
                    evidence=gap_data.get("evidence") or {},
                    status=str(gap_data.get("status") or "pending"),
                )
            )

        try:
            conversation.updated_at = utc_now()
            self._commit()
        except Exception:
            self.session.rollback()
            raise

        result["customer_message_id"] = customer_record.id
        result["assistant_message_id"] = assistant_record.id

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
