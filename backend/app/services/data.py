"""Customer Service Agent 单次运行中的事件收集器。

图节点用它整理结构化事件；请求结束后由应用服务把消息、Tool Call 与知识缺口写入 MySQL。
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4


class DataService:
    def __init__(self):
        self.tool_calls: list[dict] = []
        self.messages: list[dict] = []
        self.knowledge_gap_assessments: list[dict] = []
        self.knowledge_gap_candidates: list[dict] = []

    def record_tool_call(self, event: dict) -> dict:
        record = {**deepcopy(event), "recorded_at": datetime.now(UTC).isoformat()}
        self.tool_calls.append(record)
        return record.copy()

    def record_message(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        source: str,
    ) -> dict:
        record = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "source": source,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.messages.append(record)
        return record.copy()

    def record_knowledge_gap_assessment(
        self,
        *,
        conversation_id: str,
        customer_question: str,
        handoff_reason: str,
        is_knowledge_gap: bool,
        evidence: dict,
    ) -> dict:
        """记录每次转人工的知识缺失判定，并按需生成运营候选。"""

        assessed_at = datetime.now(UTC).isoformat()
        assessment = {
            "assessment_id": f"KGA-{uuid4().hex[:10].upper()}",
            "conversation_id": conversation_id,
            "customer_question": customer_question,
            "handoff_reason": handoff_reason,
            "is_knowledge_gap": is_knowledge_gap,
            "evidence": deepcopy(evidence),
            "assessed_at": assessed_at,
        }
        self.knowledge_gap_assessments.append(assessment)

        candidate = None
        if is_knowledge_gap:
            candidate = {
                "knowledge_gap_id": f"KGC-{uuid4().hex[:10].upper()}",
                "conversation_id": conversation_id,
                "question": customer_question,
                "reason": handoff_reason,
                "evidence": deepcopy(evidence),
                "status": "pending",
                "created_at": assessed_at,
            }
            self.knowledge_gap_candidates.append(candidate)

        return {
            "assessment": deepcopy(assessment),
            "candidate": deepcopy(candidate),
        }

    def list_knowledge_gap_candidates(self, status: str = "pending") -> list[dict]:
        return [
            deepcopy(item)
            for item in self.knowledge_gap_candidates
            if not status or item["status"] == status
        ]
