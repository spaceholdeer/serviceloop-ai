"""人工客服工作台 API 结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.customer import MessageResponse


class HandoffSummaryResponse(BaseModel):
    id: str
    conversation_id: str
    customer_id: str
    subject: str | None
    reason_code: str
    agent_summary: str
    status: str
    assigned_agent_id: str | None
    requested_at: datetime
    accepted_at: datetime | None
    resolved_at: datetime | None
    message_count: int
    latest_message: str
    updated_at: datetime


class HandoffDetailResponse(HandoffSummaryResponse):
    reason_detail: str | None
    customer_question: str
    context_package: dict[str, Any]
    messages: list[MessageResponse]


class AcceptHandoffRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=64)


class AgentReplyRequest(AcceptHandoffRequest):
    content: str = Field(min_length=1, max_length=4000)


class ResolveHandoffRequest(AcceptHandoffRequest):
    resolution_code: str = Field(default="resolved", min_length=1, max_length=64)
    action_taken: str = Field(min_length=1, max_length=4000)
    reply_to_customer: str = Field(min_length=1, max_length=4000)
    internal_notes: str | None = Field(default=None, max_length=4000)
