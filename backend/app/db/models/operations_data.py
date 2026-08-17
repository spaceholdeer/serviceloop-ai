"""Feedback、Bad Case、改进任务和数据运营运行记录。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, utc_now


class BadCaseStatus(StrEnum):
    OPEN = "open"
    TASKED = "tasked"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ImprovementTaskStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class CustomerFeedback(IdMixin, TimestampMixin, Base):
    __tablename__ = "customer_feedback"
    __table_args__ = (UniqueConstraint("conversation_id", name="uq_feedback_conversation"),)

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="customer_web", nullable=False)


class BadCase(IdMixin, TimestampMixin, Base):
    __tablename__ = "bad_cases"

    signal_key: Mapped[str] = mapped_column(String(191), nullable=False, unique=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=BadCaseStatus.OPEN.value, nullable=False, index=True
    )


class ImprovementTask(IdMixin, TimestampMixin, Base):
    __tablename__ = "improvement_tasks"
    __table_args__ = (Index("ix_improvement_tasks_status_category", "status", "category"),)

    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    bad_case_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=ImprovementTaskStatus.OPEN.value, nullable=False, index=True
    )
    owner_id: Mapped[str | None] = mapped_column(String(64))
    linked_knowledge_gap_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_gaps.id", ondelete="SET NULL")
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataOperationsRun(IdMixin, Base):
    __tablename__ = "data_operations_runs"

    operator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    processed_signal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_bad_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    findings: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

