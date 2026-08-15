"""知识文档、版本、知识缺口和 Agent 草稿模型。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utc_now


class KnowledgeDocumentStatus(StrEnum):
    PUBLISHED = "published"
    ARCHIVED = "archived"


class KnowledgeGapStatus(StrEnum):
    PENDING = "pending"
    DRAFTED = "drafted"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class KnowledgeDraftStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DISCARDED = "discarded"


class KnowledgeDocument(IdMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="operations", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=KnowledgeDocumentStatus.PUBLISHED.value, nullable=False, index=True
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    versions: Mapped[list[KnowledgeVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeVersion(IdMixin, Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_knowledge_version"),
        Index("ix_knowledge_versions_document_published", "document_id", "published_at"),
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    document: Mapped[KnowledgeDocument] = relationship(back_populates="versions")


class KnowledgeGap(IdMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_gaps"
    __table_args__ = (Index("ix_knowledge_gaps_status_created", "status", "created_at"),)

    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=KnowledgeGapStatus.PENDING.value, nullable=False, index=True
    )
    draft_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_drafts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeDraft(IdMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_drafts"
    __table_args__ = (Index("ix_knowledge_drafts_status_updated", "status", "updated_at"),)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    gap_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=KnowledgeDraftStatus.DRAFT.value, nullable=False, index=True
    )
    generated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_notes: Mapped[str | None] = mapped_column(Text)
    published_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
