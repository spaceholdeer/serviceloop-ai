"""确定性的本地演示工单服务。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import SupportTicket
from app.db.session import transactional_session
from app.repositories import BusinessRepository


class TicketService:
    def __init__(self, *, session_factory: sessionmaker[Session] | None = None):
        self.tickets: list[dict] = []
        self._session_factory = session_factory

    def create_ticket(
        self,
        *,
        customer_id: str,
        conversation_id: str,
        issue: str,
        category: str = "general",
    ) -> dict:
        clean_issue = issue.strip()
        if not clean_issue:
            return {
                "ok": False,
                "data": None,
                "error_code": "invalid_issue",
                "message": "工单问题描述不能为空。",
            }
        ticket_number = f"TKT-{uuid4().hex[:10].upper()}"
        created_at = datetime.now(UTC)
        ticket = {
            "ticket_id": ticket_number,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "category": category.strip() or "general",
            "issue": clean_issue,
            "status": "open",
            "created_at": created_at.isoformat(),
        }
        if self._session_factory is None:
            self.tickets.append(ticket)
        else:
            with transactional_session(self._session_factory) as session:
                BusinessRepository(session).add_ticket(
                    SupportTicket(
                        ticket_number=ticket_number,
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        category=ticket["category"],
                        issue=clean_issue,
                        status="open",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
        return {"ok": True, "data": ticket.copy(), "error_code": None}
