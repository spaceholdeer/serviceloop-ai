"""知识运营应用服务：持久化、草稿和 RAG 快照同步。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from openai import OpenAIError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import (
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeDraft,
    KnowledgeDraftStatus,
    KnowledgeGap,
    KnowledgeGapStatus,
    KnowledgeVersion,
)
from app.repositories import KnowledgeOperationsRepository
from app.services.knowledge import KnowledgeService


class KnowledgeRecordNotFoundError(LookupError):
    pass


class KnowledgeRecordConflictError(RuntimeError):
    pass


class KnowledgeOperationsService:
    def __init__(self, *, session: Session, knowledge: KnowledgeService):
        self.session = session
        self.knowledge = knowledge
        self.repository = KnowledgeOperationsRepository(session)

    def overview(self) -> dict[str, Any]:
        index_status = self.knowledge.status()
        return {
            "published_documents": self.repository.count(
                KnowledgeDocument, status=KnowledgeDocumentStatus.PUBLISHED.value
            ),
            "pending_gaps": self.repository.count(
                KnowledgeGap, status=KnowledgeGapStatus.PENDING.value
            ),
            "open_drafts": self.repository.count(
                KnowledgeDraft, status=KnowledgeDraftStatus.DRAFT.value
            ),
            "index": {**index_status, "storage": "mysql_backed_runtime_index"},
        }

    def list_documents(self, status: str | None = None) -> list[dict[str, Any]]:
        return [self._document_payload(item) for item in self.repository.list_documents(status)]

    def get_document(self, document_id: str) -> dict[str, Any]:
        document = self._require_document(document_id)
        payload = self._document_payload(document)
        payload["versions"] = [
            self._version_payload(item) for item in self.repository.list_versions(document_id)
        ]
        return payload

    def list_versions(self, document_id: str) -> list[dict[str, Any]]:
        self._require_document(document_id)
        return [
            self._version_payload(item) for item in self.repository.list_versions(document_id)
        ]

    def publish_document(
        self,
        *,
        title: str,
        content: str,
        operator_id: str,
        document_id: str | None = None,
        source: str = "operations",
    ) -> dict[str, Any]:
        document = self._stage_document(
            title=title,
            content=content,
            operator_id=operator_id,
            document_id=document_id,
            source=source,
        )
        self._commit_and_rebuild()
        return self._document_payload(document)

    def archive_document(self, document_id: str) -> dict[str, Any]:
        document = self._require_document(document_id)
        if document.status == KnowledgeDocumentStatus.ARCHIVED.value:
            return self._document_payload(document)
        document.status = KnowledgeDocumentStatus.ARCHIVED.value
        document.updated_at = utc_now()
        self._commit_and_rebuild()
        return self._document_payload(document)

    def list_gaps(
        self,
        *,
        status: str | None = KnowledgeGapStatus.PENDING.value,
        ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return [self._gap_payload(item) for item in self.repository.list_gaps(status=status, ids=ids)]

    def get_gap(self, gap_id: str) -> dict[str, Any]:
        gap = self.repository.get_gap(gap_id)
        if gap is None:
            raise KnowledgeRecordNotFoundError(gap_id)
        return self._gap_payload(gap)

    def dismiss_gap(self, gap_id: str) -> dict[str, Any]:
        gap = self.repository.get_gap(gap_id)
        if gap is None:
            raise KnowledgeRecordNotFoundError(gap_id)
        gap.status = KnowledgeGapStatus.DISMISSED.value
        gap.updated_at = utc_now()
        self._commit()
        return self._gap_payload(gap)

    def list_drafts(self, status: str | None = None) -> list[dict[str, Any]]:
        return [self._draft_payload(item) for item in self.repository.list_drafts(status)]

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        return self._draft_payload(self._require_draft(draft_id))

    def create_draft(
        self,
        *,
        title: str,
        content: str,
        gap_ids: list[str],
        generated_by: str,
        generation_notes: str | None = None,
    ) -> dict[str, Any]:
        gaps = self.repository.list_gaps(ids=gap_ids)
        if len(gaps) != len(set(gap_ids)):
            raise KnowledgeRecordNotFoundError("one or more knowledge gaps do not exist")
        draft = KnowledgeDraft(
            id=f"KDR-{uuid4().hex[:12].upper()}",
            title=title.strip(),
            content=content.strip(),
            gap_ids=list(dict.fromkeys(gap_ids)),
            generated_by=generated_by,
            generation_notes=generation_notes,
        )
        if not draft.title or not draft.content:
            raise ValueError("知识草稿标题和正文不能为空。")
        self.repository.add(draft)
        for gap in gaps:
            gap.status = KnowledgeGapStatus.DRAFTED.value
            gap.draft_id = draft.id
            gap.updated_at = utc_now()
        self._commit()
        return self._draft_payload(draft)

    def update_draft(self, *, draft_id: str, title: str, content: str) -> dict[str, Any]:
        draft = self._require_draft(draft_id)
        if draft.status != KnowledgeDraftStatus.DRAFT.value:
            raise KnowledgeRecordConflictError("only open drafts can be edited")
        if not title.strip() or not content.strip():
            raise ValueError("知识草稿标题和正文不能为空。")
        draft.title = title.strip()
        draft.content = content.strip()
        draft.updated_at = utc_now()
        self._commit()
        return self._draft_payload(draft)

    def publish_draft(
        self,
        *,
        draft_id: str,
        operator_id: str,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        draft = self._require_draft(draft_id)
        if draft.status != KnowledgeDraftStatus.DRAFT.value:
            raise KnowledgeRecordConflictError("draft is not publishable")
        document = self._stage_document(
            title=draft.title,
            content=draft.content,
            operator_id=operator_id,
            document_id=document_id,
            source="knowledge_operations_agent",
        )
        now = utc_now()
        draft.status = KnowledgeDraftStatus.PUBLISHED.value
        draft.published_document_id = document.id
        draft.published_at = now
        draft.updated_at = now
        for gap in self.repository.list_gaps(ids=draft.gap_ids):
            gap.status = KnowledgeGapStatus.RESOLVED.value
            gap.resolved_at = now
            gap.updated_at = now
        self._commit_and_rebuild()
        return {
            "draft": self._draft_payload(draft),
            "document": self._document_payload(document),
        }

    def _stage_document(
        self,
        *,
        title: str,
        content: str,
        operator_id: str,
        document_id: str | None,
        source: str,
    ) -> KnowledgeDocument:
        clean_title = title.strip()
        clean_content = content.strip()
        if not clean_title or not clean_content:
            raise ValueError("知识标题和正文不能为空。")
        document = self.repository.get_document(document_id) if document_id else None
        if document is None:
            document = KnowledgeDocument(
                id=document_id or str(uuid4()),
                title=clean_title,
                source=source,
                status=KnowledgeDocumentStatus.PUBLISHED.value,
                current_version=1,
            )
            self.repository.add(document)
            version_number = 1
        else:
            version_number = document.current_version + 1
            document.title = clean_title
            document.source = source
            document.status = KnowledgeDocumentStatus.PUBLISHED.value
            document.current_version = version_number
            document.updated_at = utc_now()
        self.repository.add(
            KnowledgeVersion(
                document_id=document.id,
                version=version_number,
                title=clean_title,
                content=clean_content,
                created_by=operator_id,
            )
        )
        self.session.flush()
        return document

    def _commit_and_rebuild(self) -> None:
        try:
            self.session.flush()
            self.knowledge.replace_all(self.repository.list_published_payloads())
            self.session.commit()
        except (OpenAIError, RuntimeError, SQLAlchemyError, ValueError):
            self.session.rollback()
            self.knowledge.replace_all(self.repository.list_published_payloads())
            raise

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _require_document(self, document_id: str) -> KnowledgeDocument:
        document = self.repository.get_document(document_id)
        if document is None:
            raise KnowledgeRecordNotFoundError(document_id)
        return document

    def _require_draft(self, draft_id: str) -> KnowledgeDraft:
        draft = self.repository.get_draft(draft_id)
        if draft is None:
            raise KnowledgeRecordNotFoundError(draft_id)
        return draft

    def _document_payload(self, document: KnowledgeDocument) -> dict[str, Any]:
        current = self.repository.get_current_version(document)
        return {
            "id": document.id,
            "title": document.title,
            "source": document.source,
            "status": document.status,
            "current_version": document.current_version,
            "content": current.content if current else "",
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }

    @staticmethod
    def _version_payload(version: KnowledgeVersion) -> dict[str, Any]:
        return {
            "id": version.id,
            "document_id": version.document_id,
            "version": version.version,
            "title": version.title,
            "content": version.content,
            "created_by": version.created_by,
            "published_at": version.published_at,
        }

    def _gap_payload(self, gap: KnowledgeGap) -> dict[str, Any]:
        resolution = self.repository.latest_resolution_for_conversation(gap.conversation_id)
        return {
            "id": gap.id,
            "conversation_id": gap.conversation_id,
            "question": gap.question,
            "reason": gap.reason,
            "evidence": gap.evidence,
            "status": gap.status,
            "draft_id": gap.draft_id,
            "human_resolution": (
                {
                    "resolution_code": resolution.resolution_code,
                    "action_taken": resolution.action_taken,
                    "reply_to_customer": resolution.reply_to_customer,
                }
                if resolution
                else None
            ),
            "created_at": gap.created_at,
            "updated_at": gap.updated_at,
        }

    @staticmethod
    def _draft_payload(draft: KnowledgeDraft) -> dict[str, Any]:
        return {
            "id": draft.id,
            "title": draft.title,
            "content": draft.content,
            "gap_ids": draft.gap_ids,
            "status": draft.status,
            "generated_by": draft.generated_by,
            "generation_notes": draft.generation_notes,
            "published_document_id": draft.published_document_id,
            "published_at": draft.published_at,
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
        }
