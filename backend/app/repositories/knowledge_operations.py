"""知识运营的数据访问层。"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    HumanResolution,
    KnowledgeDocument,
    KnowledgeDraft,
    KnowledgeGap,
    KnowledgeVersion,
)


class KnowledgeOperationsRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, record: object) -> None:
        self.session.add(record)

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return self.session.get(KnowledgeDocument, document_id)

    def get_current_version(self, document: KnowledgeDocument) -> KnowledgeVersion | None:
        statement = select(KnowledgeVersion).where(
            KnowledgeVersion.document_id == document.id,
            KnowledgeVersion.version == document.current_version,
        )
        return self.session.scalar(statement)

    def list_documents(self, status: str | None = None) -> list[KnowledgeDocument]:
        statement: Select[tuple[KnowledgeDocument]] = select(KnowledgeDocument)
        if status:
            statement = statement.where(KnowledgeDocument.status == status)
        statement = statement.order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id)
        return list(self.session.scalars(statement))

    def list_published_payloads(self) -> list[dict]:
        statement = (
            select(KnowledgeDocument, KnowledgeVersion)
            .join(
                KnowledgeVersion,
                (KnowledgeVersion.document_id == KnowledgeDocument.id)
                & (KnowledgeVersion.version == KnowledgeDocument.current_version),
            )
            .where(KnowledgeDocument.status == "published")
            .order_by(KnowledgeDocument.updated_at, KnowledgeDocument.id)
        )
        return [
            {
                "id": document.id,
                "title": version.title,
                "content": version.content,
                "version": version.version,
                "source": document.source,
            }
            for document, version in self.session.execute(statement).all()
        ]

    def list_versions(self, document_id: str) -> list[KnowledgeVersion]:
        statement = (
            select(KnowledgeVersion)
            .where(KnowledgeVersion.document_id == document_id)
            .order_by(KnowledgeVersion.version.desc())
        )
        return list(self.session.scalars(statement))

    def get_gap(self, gap_id: str) -> KnowledgeGap | None:
        return self.session.get(KnowledgeGap, gap_id)

    def list_gaps(
        self,
        *,
        status: str | None = None,
        ids: Sequence[str] | None = None,
    ) -> list[KnowledgeGap]:
        statement: Select[tuple[KnowledgeGap]] = select(KnowledgeGap)
        if status:
            statement = statement.where(KnowledgeGap.status == status)
        if ids is not None:
            if not ids:
                return []
            statement = statement.where(KnowledgeGap.id.in_(ids))
        statement = statement.order_by(KnowledgeGap.created_at, KnowledgeGap.id)
        return list(self.session.scalars(statement))

    def latest_resolution_for_conversation(
        self, conversation_id: str | None
    ) -> HumanResolution | None:
        if not conversation_id:
            return None
        statement = (
            select(HumanResolution)
            .where(HumanResolution.conversation_id == conversation_id)
            .order_by(HumanResolution.created_at.desc(), HumanResolution.id.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_draft(self, draft_id: str) -> KnowledgeDraft | None:
        return self.session.get(KnowledgeDraft, draft_id)

    def list_drafts(self, status: str | None = None) -> list[KnowledgeDraft]:
        statement: Select[tuple[KnowledgeDraft]] = select(KnowledgeDraft)
        if status:
            statement = statement.where(KnowledgeDraft.status == status)
        statement = statement.order_by(KnowledgeDraft.updated_at.desc(), KnowledgeDraft.id)
        return list(self.session.scalars(statement))

    def count(self, model: type, *, status: str | None = None) -> int:
        statement = select(func.count()).select_from(model)
        if status is not None:
            statement = statement.where(model.status == status)
        return int(self.session.scalar(statement) or 0)
