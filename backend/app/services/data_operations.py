"""Feedback、Bad Case、改进任务和飞轮回流应用服务。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import (
    BadCase,
    BadCaseStatus,
    Conversation,
    CustomerFeedback,
    DataOperationsRun,
    ImprovementTask,
    ImprovementTaskStatus,
    KnowledgeGap,
)
from app.repositories import DataOperationsRepository


class DataRecordNotFoundError(LookupError):
    pass


class DataRecordConflictError(RuntimeError):
    pass


class DataOperationsService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = DataOperationsRepository(session)

    def submit_feedback(
        self,
        *,
        conversation_id: str,
        customer_id: str,
        rating: int,
        comment: str | None,
    ) -> CustomerFeedback:
        conversation = self.session.get(Conversation, conversation_id)
        if conversation is None or conversation.customer_id != customer_id:
            raise DataRecordNotFoundError("conversation not found")
        feedback = self.repository.get_feedback_for_conversation(conversation_id)
        if feedback is None:
            feedback = CustomerFeedback(
                conversation_id=conversation_id,
                customer_id=customer_id,
                rating=rating,
                comment=comment.strip() if comment else None,
            )
            self.repository.add_feedback(feedback)
        else:
            feedback.rating = rating
            feedback.comment = comment.strip() if comment else None
            feedback.updated_at = utc_now()
        self._commit()
        return feedback

    def overview(self) -> dict[str, Any]:
        runs = self.repository.list_runs(limit=1)
        return {**self.repository.counts(), "latest_run": runs[0] if runs else None}

    def list_bad_cases(self, status: str | None = None) -> list[BadCase]:
        return self.repository.list_bad_cases(status)

    def list_improvement_tasks(self, status: str | None = None) -> list[ImprovementTask]:
        return self.repository.list_improvement_tasks(status)

    def list_runs(self, limit: int = 10) -> list[DataOperationsRun]:
        return self.repository.list_runs(limit)

    def collect_signals(self) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        for feedback in self.repository.list_negative_feedback():
            signals.append(
                {
                    "signal_key": f"feedback:{feedback.id}",
                    "source_type": "feedback",
                    "source_id": feedback.id,
                    "conversation_id": feedback.conversation_id,
                    "category": "experience",
                    "severity": "high" if feedback.rating == 1 else "medium",
                    "summary": feedback.comment or f"客户对本次服务评分 {feedback.rating} 分。",
                    "evidence": {"rating": feedback.rating, "comment": feedback.comment},
                }
            )
        for call in self.repository.list_failed_tool_calls():
            signals.append(
                {
                    "signal_key": f"tool_call:{call.id}",
                    "source_type": "tool_call",
                    "source_id": call.id,
                    "conversation_id": call.conversation_id,
                    "category": "tool",
                    "severity": "high",
                    "summary": f"{call.service_name}.{call.operation} 调用失败。",
                    "evidence": {
                        "service_name": call.service_name,
                        "operation": call.operation,
                        "input": call.input_payload,
                        "error": call.error_message,
                    },
                }
            )
        for handoff in self.repository.list_actionable_handoffs():
            category = (
                "knowledge"
                if handoff.reason_code in {"knowledge_insufficient", "policy_unclear"}
                else "tool"
                if handoff.reason_code == "tool_failed"
                else "process"
            )
            signals.append(
                {
                    "signal_key": f"handoff:{handoff.id}",
                    "source_type": "handoff",
                    "source_id": handoff.id,
                    "conversation_id": handoff.conversation_id,
                    "category": category,
                    "severity": "medium" if category == "knowledge" else "high",
                    "summary": handoff.agent_summary,
                    "evidence": {
                        "reason_code": handoff.reason_code,
                        "customer_question": handoff.customer_question,
                        "context_package": handoff.context_package,
                    },
                }
            )
        return signals

    def materialize_bad_cases(self, signals: list[dict[str, Any]]) -> list[BadCase]:
        created: list[BadCase] = []
        for signal in signals:
            if self.repository.get_bad_case_by_signal(signal["signal_key"]):
                continue
            bad_case = BadCase(**signal)
            self.repository.add_bad_case(bad_case)
            created.append(bad_case)
        self.session.flush()
        return created

    def group_open_cases(self) -> dict[str, list[BadCase]]:
        groups: dict[str, list[BadCase]] = defaultdict(list)
        for bad_case in self.repository.list_bad_cases(BadCaseStatus.OPEN.value):
            groups[bad_case.category].append(bad_case)
        return dict(groups)

    def create_improvement_tasks(
        self, groups: dict[str, list[BadCase]]
    ) -> list[ImprovementTask]:
        labels = {
            "knowledge": (
                "补齐重复缺失的服务规则",
                "核对关联人工结论，将可靠规则补入知识库并验证检索命中。",
            ),
            "tool": (
                "修复失败的业务工具调用",
                "复现失败调用，修复数据或服务错误，并用同类请求验证恢复。",
            ),
            "experience": (
                "复盘低满意度服务会话",
                "阅读客户反馈和完整会话，确认是知识、工具还是服务表达问题。",
            ),
            "process": (
                "完善高风险场景处理流程",
                "核对人工处理结论，明确可自动化边界和必须保留的人工节点。",
            ),
        }
        tasks: list[ImprovementTask] = []
        for category, cases in groups.items():
            if not cases:
                continue
            title, description = labels.get(
                category,
                ("复盘客服异常案例", "阅读证据并记录可验证的改进动作。"),
            )
            task = ImprovementTask(
                category=category,
                title=title,
                description=description,
                bad_case_ids=[item.id for item in cases],
                evidence={
                    "case_count": len(cases),
                    "conversation_ids": sorted(
                        {item.conversation_id for item in cases if item.conversation_id}
                    ),
                    "summaries": [item.summary for item in cases[:8]],
                },
            )
            self.repository.add_improvement_task(task)
            for item in cases:
                item.status = BadCaseStatus.TASKED.value
            tasks.append(task)
        self.session.flush()
        return tasks

    def record_run(
        self,
        *,
        operator_id: str,
        signal_count: int,
        created_case_count: int,
        tasks: list[ImprovementTask],
    ) -> DataOperationsRun:
        findings = [
            {
                "category": task.category,
                "title": task.title,
                "case_count": len(task.bad_case_ids),
                "task_id": task.id,
            }
            for task in tasks
        ]
        summary = (
            f"处理 {signal_count} 条运行信号，新建 {created_case_count} 个 Bad Case，"
            f"形成 {len(tasks)} 项改进任务。"
            if signal_count
            else "当前没有新的低评分、工具失败或异常转人工信号。"
        )
        run = DataOperationsRun(
            operator_id=operator_id,
            status="completed",
            processed_signal_count=signal_count,
            created_bad_case_count=created_case_count,
            created_task_count=len(tasks),
            summary=summary,
            findings=findings,
        )
        self.repository.add_run(run)
        self._commit()
        return run

    def resolve_task(
        self, *, task_id: str, operator_id: str, resolution_notes: str
    ) -> ImprovementTask:
        task = self._get_task(task_id)
        if task.status == ImprovementTaskStatus.RESOLVED.value:
            raise DataRecordConflictError("improvement task is already resolved")
        task.status = ImprovementTaskStatus.RESOLVED.value
        task.owner_id = operator_id
        task.resolution_notes = resolution_notes.strip()
        task.resolved_at = utc_now()
        for bad_case_id in task.bad_case_ids:
            bad_case = self.repository.get_bad_case(bad_case_id)
            if bad_case:
                bad_case.status = BadCaseStatus.RESOLVED.value
        self._commit()
        return task

    def promote_task_to_knowledge_gap(
        self, *, task_id: str, operator_id: str
    ) -> tuple[ImprovementTask, KnowledgeGap]:
        task = self._get_task(task_id)
        if task.category not in {"knowledge", "experience"}:
            raise DataRecordConflictError("only knowledge or experience tasks can become a gap")
        if task.linked_knowledge_gap_id:
            gap = self.session.get(KnowledgeGap, task.linked_knowledge_gap_id)
            if gap:
                return task, gap
        cases = [
            item
            for bad_case_id in task.bad_case_ids
            if (item := self.repository.get_bad_case(bad_case_id)) is not None
        ]
        conversation_id = next((item.conversation_id for item in cases if item.conversation_id), None)
        existing = self.repository.find_pending_gap(conversation_id)
        if existing:
            gap = existing
        else:
            question = (
                self.repository.latest_customer_question(conversation_id)
                if conversation_id
                else None
            ) or task.title
            gap = KnowledgeGap(
                id=f"KGC-DATA-{uuid4().hex[:12].upper()}",
                conversation_id=conversation_id,
                question=question,
                reason="data_operations_followup",
                evidence={
                    "improvement_task_id": task.id,
                    "bad_case_ids": task.bad_case_ids,
                    "summaries": task.evidence.get("summaries", []),
                    "promoted_by": operator_id,
                },
            )
            self.session.add(gap)
            self.session.flush()
        task.linked_knowledge_gap_id = gap.id
        task.owner_id = operator_id
        self._commit()
        return task, gap

    def _get_task(self, task_id: str) -> ImprovementTask:
        task = self.repository.get_improvement_task(task_id)
        if task is None:
            raise DataRecordNotFoundError(task_id)
        return task

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

