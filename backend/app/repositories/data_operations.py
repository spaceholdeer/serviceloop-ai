"""数据运营飞轮的数据访问。"""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    BadCase,
    CustomerFeedback,
    DataOperationsRun,
    Handoff,
    ImprovementTask,
    KnowledgeGap,
    Message,
    ToolCall,
)


class DataOperationsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_feedback_for_conversation(self, conversation_id: str) -> CustomerFeedback | None:
        return self.session.scalar(
            select(CustomerFeedback).where(CustomerFeedback.conversation_id == conversation_id)
        )

    def add_feedback(self, feedback: CustomerFeedback) -> None:
        self.session.add(feedback)

    def list_negative_feedback(self) -> list[CustomerFeedback]:
        return list(
            self.session.scalars(
                select(CustomerFeedback)
                .where(CustomerFeedback.rating <= 2)
                .order_by(CustomerFeedback.created_at.desc())
            )
        )

    def list_failed_tool_calls(self) -> list[ToolCall]:
        return list(
            self.session.scalars(
                select(ToolCall)
                .where(ToolCall.status == "failed")
                .order_by(ToolCall.created_at.desc())
            )
        )

    def list_actionable_handoffs(self) -> list[Handoff]:
        return list(
            self.session.scalars(
                select(Handoff)
                .where(
                    Handoff.reason_code.in_(
                        ["knowledge_insufficient", "policy_unclear", "tool_failed", "risk_case"]
                    )
                )
                .order_by(Handoff.requested_at.desc())
            )
        )

    def get_bad_case_by_signal(self, signal_key: str) -> BadCase | None:
        return self.session.scalar(select(BadCase).where(BadCase.signal_key == signal_key))

    def get_bad_case(self, bad_case_id: str) -> BadCase | None:
        return self.session.get(BadCase, bad_case_id)

    def add_bad_case(self, bad_case: BadCase) -> None:
        self.session.add(bad_case)

    def list_bad_cases(self, status: str | None = None) -> list[BadCase]:
        statement: Select[tuple[BadCase]] = select(BadCase)
        if status:
            statement = statement.where(BadCase.status == status)
        return list(self.session.scalars(statement.order_by(BadCase.created_at.desc())))

    def get_improvement_task(self, task_id: str) -> ImprovementTask | None:
        return self.session.get(ImprovementTask, task_id)

    def add_improvement_task(self, task: ImprovementTask) -> None:
        self.session.add(task)

    def list_improvement_tasks(self, status: str | None = None) -> list[ImprovementTask]:
        statement: Select[tuple[ImprovementTask]] = select(ImprovementTask)
        if status:
            statement = statement.where(ImprovementTask.status == status)
        return list(self.session.scalars(statement.order_by(ImprovementTask.created_at.desc())))

    def add_run(self, run: DataOperationsRun) -> None:
        self.session.add(run)

    def list_runs(self, limit: int = 10) -> list[DataOperationsRun]:
        return list(
            self.session.scalars(
                select(DataOperationsRun)
                .order_by(DataOperationsRun.created_at.desc())
                .limit(limit)
            )
        )

    def latest_customer_question(self, conversation_id: str) -> str | None:
        return self.session.scalar(
            select(Message.content)
            .where(Message.conversation_id == conversation_id, Message.role == "customer")
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )

    def find_pending_gap(self, conversation_id: str | None) -> KnowledgeGap | None:
        if not conversation_id:
            return None
        return self.session.scalar(
            select(KnowledgeGap)
            .where(
                KnowledgeGap.conversation_id == conversation_id,
                KnowledgeGap.status.in_(["pending", "drafted"]),
            )
            .order_by(KnowledgeGap.created_at.desc())
            .limit(1)
        )

    def counts(self) -> dict[str, int]:
        def count(model: type, *conditions: object) -> int:
            statement = select(func.count()).select_from(model)
            if conditions:
                statement = statement.where(*conditions)
            return int(self.session.scalar(statement) or 0)

        return {
            "feedback_total": count(CustomerFeedback),
            "negative_feedback": count(CustomerFeedback, CustomerFeedback.rating <= 2),
            "failed_tool_calls": count(ToolCall, ToolCall.status == "failed"),
            "open_bad_cases": count(BadCase, BadCase.status == "open"),
            "open_improvement_tasks": count(ImprovementTask, ImprovementTask.status == "open"),
        }

