"""用户端客服聊天 API 结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CustomerChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, min_length=1, max_length=36)
    customer_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


class CustomerHumanMessageRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=4000)


class CustomerChatResponse(BaseModel):
    conversation_id: str
    conversation_status: str
    customer_message_id: str
    assistant_message_id: str
    answer: str
    handoff_required: bool
    handoff_reason: str | None = None
    handoff: dict[str, Any] | None = None
    tool_events: list[dict[str, Any]]
    original_query: str | None = None
    rewritten_query: str | None = None
    rewrite_count: int = 0
    retrieval_attempts: list[dict[str, Any]] = Field(default_factory=list)
    customer_intent: str | None = None
    evidence_decision: dict[str, Any] | None = None
    knowledge_gap_assessment: dict[str, Any] | None = None
    knowledge_gap_candidate: dict[str, Any] | None = None


class ConversationCreateRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    subject: str | None = Field(default=None, max_length=255)


class ConversationResponse(BaseModel):
    id: str
    customer_id: str
    channel: str
    subject: str | None
    status: str
    started_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    source: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
