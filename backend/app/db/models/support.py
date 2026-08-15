"""人工接管和人工处理结论模型。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utc_now


class HandoffStatus(StrEnum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    ACTIVE = "active"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class Handoff(IdMixin, TimestampMixin, Base):
    __tablename__ = "handoffs"
    __table_args__ = (Index("ix_handoffs_status_requested", "status", "requested_at"),)

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason_detail: Mapped[str | None] = mapped_column(Text)
    customer_question: Mapped[str] = mapped_column(Text, nullable=False)
    agent_summary: Mapped[str] = mapped_column(Text, nullable=False)
    context_package: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=HandoffStatus.QUEUED.value, nullable=False
    )
    assigned_agent_id: Mapped[str | None] = mapped_column(String(64), index=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    conversation: Mapped[Conversation] = relationship(back_populates="handoffs")
    resolution: Mapped[HumanResolution | None] = relationship(
        back_populates="handoff", cascade="all, delete-orphan", uselist=False
    )


class HumanResolution(IdMixin, Base):
    __tablename__ = "human_resolutions"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    handoff_id: Mapped[str] = mapped_column(
        ForeignKey("handoffs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resolution_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    reply_to_customer: Mapped[str] = mapped_column(Text, nullable=False)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="resolutions")
    handoff: Mapped[Handoff] = relationship(back_populates="resolution")


from app.db.models.conversation import Conversation
