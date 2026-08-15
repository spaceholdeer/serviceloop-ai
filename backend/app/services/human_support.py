"""人工客服领取、对话和解决接管任务的应用服务。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import (
    ConversationStatus,
    Handoff,
    HandoffStatus,
    HumanResolution,
    Message,
    MessageRole,
)
from app.repositories import HumanSupportRepository


class HandoffNotFoundError(LookupError):
    pass


class HandoffConflictError(RuntimeError):
    pass


class HumanSupportService:
    """保持人工接管规则确定性，所有写操作在请求事务内提交或回滚。"""

    def __init__(self, session: Session):
        self.session = session
        self.repository = HumanSupportRepository(session)

    def list_handoffs(self, statuses: list[str] | None = None) -> list[dict[str, Any]]:
        return [self._summary(item) for item in self.repository.list_handoffs(statuses)]

    def get_handoff(self, handoff_id: str) -> dict[str, Any]:
        handoff = self._get(handoff_id)
        return self._detail(handoff)

    def accept(self, *, handoff_id: str, agent_id: str) -> dict[str, Any]:
        handoff = self._get(handoff_id)
        if handoff.status in {HandoffStatus.RESOLVED.value, HandoffStatus.CANCELLED.value}:
            raise HandoffConflictError("handoff is already closed")
        if handoff.assigned_agent_id and handoff.assigned_agent_id != agent_id:
            raise HandoffConflictError("handoff is assigned to another agent")

        handoff.assigned_agent_id = agent_id
        handoff.accepted_at = handoff.accepted_at or utc_now()
        handoff.status = HandoffStatus.ACTIVE.value
        handoff.conversation.status = ConversationStatus.HUMAN_ACTIVE.value
        handoff.conversation.updated_at = utc_now()
        self._commit()
        return self._detail(handoff)

    def reply(self, *, handoff_id: str, agent_id: str, content: str) -> Message:
        handoff = self._require_active_assignment(handoff_id, agent_id)
        message = Message(
            conversation_id=handoff.conversation_id,
            role=MessageRole.HUMAN_AGENT.value,
            source="human_support_console",
            content=content.strip(),
        )
        self.repository.add_message(message)
        handoff.conversation.updated_at = utc_now()
        self._commit()
        return message

    def resolve(
        self,
        *,
        handoff_id: str,
        agent_id: str,
        resolution_code: str,
        action_taken: str,
        reply_to_customer: str,
        internal_notes: str | None,
    ) -> dict[str, Any]:
        handoff = self._require_active_assignment(handoff_id, agent_id)
        final_reply = Message(
            conversation_id=handoff.conversation_id,
            role=MessageRole.HUMAN_AGENT.value,
            source="human_support_console",
            content=reply_to_customer.strip(),
        )
        resolution = HumanResolution(
            conversation_id=handoff.conversation_id,
            handoff_id=handoff.id,
            agent_id=agent_id,
            resolution_code=resolution_code.strip(),
            action_taken=action_taken.strip(),
            reply_to_customer=reply_to_customer.strip(),
            internal_notes=internal_notes.strip() if internal_notes else None,
        )
        self.repository.add_message(final_reply)
        self.repository.add_resolution(resolution)
        now = utc_now()
        handoff.status = HandoffStatus.RESOLVED.value
        handoff.resolved_at = now
        handoff.conversation.status = ConversationStatus.RESOLVED.value
        handoff.conversation.ended_at = now
        handoff.conversation.updated_at = now
        self._commit()
        return self._detail(handoff)

    def _get(self, handoff_id: str) -> Handoff:
        handoff = self.repository.get_handoff(handoff_id)
        if handoff is None:
            raise HandoffNotFoundError(handoff_id)
        return handoff

    def _require_active_assignment(self, handoff_id: str, agent_id: str) -> Handoff:
        handoff = self._get(handoff_id)
        if handoff.status != HandoffStatus.ACTIVE.value:
            raise HandoffConflictError("handoff is not active")
        if handoff.assigned_agent_id != agent_id:
            raise HandoffConflictError("handoff is assigned to another agent")
        return handoff

    def _summary(self, handoff: Handoff) -> dict[str, Any]:
        messages = self.repository.list_messages(handoff.conversation_id)
        latest = messages[-1] if messages else None
        return {
            "id": handoff.id,
            "conversation_id": handoff.conversation_id,
            "customer_id": handoff.conversation.customer_id,
            "subject": handoff.conversation.subject,
            "reason_code": handoff.reason_code,
            "agent_summary": handoff.agent_summary,
            "status": handoff.status,
            "assigned_agent_id": handoff.assigned_agent_id,
            "requested_at": handoff.requested_at,
            "accepted_at": handoff.accepted_at,
            "resolved_at": handoff.resolved_at,
            "message_count": len(messages),
            "latest_message": latest.content if latest else handoff.customer_question,
            "updated_at": handoff.conversation.updated_at,
        }

    def _detail(self, handoff: Handoff) -> dict[str, Any]:
        return {
            **self._summary(handoff),
            "reason_detail": handoff.reason_detail,
            "customer_question": handoff.customer_question,
            "context_package": handoff.context_package,
            "messages": self.repository.list_messages(handoff.conversation_id),
        }

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
