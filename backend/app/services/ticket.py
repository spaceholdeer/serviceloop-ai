"""确定性的本地演示工单服务。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


class TicketService:
    def __init__(self):
        self.tickets: list[dict] = []

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
        ticket = {
            "ticket_id": f"TKT-{uuid4().hex[:10].upper()}",
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "category": category.strip() or "general",
            "issue": clean_issue,
            "status": "open",
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.tickets.append(ticket)
        return {"ok": True, "data": ticket.copy(), "error_code": None}
