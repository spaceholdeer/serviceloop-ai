"""确定性的本地演示人工接管服务。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


class HumanService:
    def __init__(self):
        self.handoffs: list[dict] = []

    def request_handoff(
        self,
        *,
        customer_id: str,
        conversation_id: str,
        reason_code: str,
        agent_summary: str,
        customer_question: str,
        context_package: dict,
    ) -> dict:
        handoff = {
            "handoff_id": f"HOF-{uuid4().hex[:10].upper()}",
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "reason_code": reason_code,
            "agent_summary": agent_summary,
            "customer_question": customer_question,
            "context_package": context_package,
            "status": "queued",
            "requested_at": datetime.now(UTC).isoformat(),
        }
        self.handoffs.append(handoff)
        return {"ok": True, "data": handoff.copy(), "error_code": None}
