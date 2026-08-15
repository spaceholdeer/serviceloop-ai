"""运营后台知识闭环的请求和响应结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentWriteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    operator_id: str = Field(default="operations-demo-001", min_length=1, max_length=64)
    source: str = Field(default="operations", min_length=1, max_length=64)


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    content: str
    source: str
    status: str
    current_version: int
    created_at: datetime
    updated_at: datetime


class KnowledgeVersionResponse(BaseModel):
    id: str
    document_id: str
    version: int
    title: str
    content: str
    created_by: str
    published_at: datetime


class HumanResolutionContext(BaseModel):
    resolution_code: str
    action_taken: str
    reply_to_customer: str


class KnowledgeGapResponse(BaseModel):
    id: str
    conversation_id: str | None
    question: str
    reason: str
    evidence: dict[str, Any]
    status: str
    draft_id: str | None
    human_resolution: HumanResolutionContext | None
    created_at: datetime
    updated_at: datetime


class KnowledgeDraftResponse(BaseModel):
    id: str
    title: str
    content: str
    gap_ids: list[str]
    status: str
    generated_by: str
    generation_notes: str | None
    published_document_id: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeDraftUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class KnowledgeDraftPublishRequest(BaseModel):
    operator_id: str = Field(default="operations-demo-001", min_length=1, max_length=64)
    document_id: str | None = Field(default=None, max_length=36)


class KnowledgeAgentRunRequest(BaseModel):
    gap_ids: list[str] = Field(default_factory=list)
    operator_id: str = Field(default="operations-demo-001", min_length=1, max_length=64)


class KnowledgeAgentRunResponse(BaseModel):
    processed_gap_count: int
    drafts: list[KnowledgeDraftResponse]
    message: str


class KnowledgePublishResult(BaseModel):
    draft: KnowledgeDraftResponse
    document: KnowledgeDocumentResponse


class OperationsOverviewResponse(BaseModel):
    published_documents: int
    pending_gaps: int
    open_drafts: int
    index: dict[str, Any]
