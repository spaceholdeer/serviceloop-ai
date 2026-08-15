"""会话、消息和工具调用模型。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utc_now


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    WAITING_FOR_HUMAN = "waiting_for_human"
    HUMAN_ACTIVE = "human_active"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MessageRole(StrEnum):
    CUSTOMER = "customer"
    ASSISTANT = "assistant"
    HUMAN_AGENT = "human_agent"
    SYSTEM = "system"


class ToolCallStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="web", nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32), default=ConversationStatus.ACTIVE.value, nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    tool_calls: Mapped[list[ToolCall]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    handoffs: Mapped[list[Handoff]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    resolutions: Mapped[list[HumanResolution]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(IdMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    tool_calls: Mapped[list[ToolCall]] = relationship(back_populates="message")


class ToolCall(IdMixin, Base):
    __tablename__ = "tool_calls"
    __table_args__ = (Index("ix_tool_calls_conversation_created", "conversation_id", "created_at"),)

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    service_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="tool_calls")
    message: Mapped[Message | None] = relationship(back_populates="tool_calls")


from app.db.models.support import Handoff, HumanResolution
