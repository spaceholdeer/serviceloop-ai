"""ServiceLoop 客服数据中台 ORM 模型。"""

from app.db.models.business import CustomerOrder, Shipment, SupportTicket
from app.db.models.conversation import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    ToolCall,
    ToolCallStatus,
)
from app.db.models.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeDraft,
    KnowledgeDraftStatus,
    KnowledgeGap,
    KnowledgeGapStatus,
    KnowledgeVersion,
)
from app.db.models.operations_data import (
    BadCase,
    BadCaseStatus,
    CustomerFeedback,
    DataOperationsRun,
    ImprovementTask,
    ImprovementTaskStatus,
)
from app.db.models.support import Handoff, HandoffStatus, HumanResolution

__all__ = [
    "BadCase",
    "BadCaseStatus",
    "Conversation",
    "ConversationStatus",
    "CustomerFeedback",
    "CustomerOrder",
    "DataOperationsRun",
    "Handoff",
    "HandoffStatus",
    "HumanResolution",
    "ImprovementTask",
    "ImprovementTaskStatus",
    "KnowledgeDocument",
    "KnowledgeDocumentStatus",
    "KnowledgeDraft",
    "KnowledgeDraftStatus",
    "KnowledgeGap",
    "KnowledgeGapStatus",
    "KnowledgeVersion",
    "Message",
    "MessageRole",
    "Shipment",
    "SupportTicket",
    "ToolCall",
    "ToolCallStatus",
]
