"""客户对话闭环的数据访问。"""

from __future__ import annotations

from sqlalchemy import Select, case, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Handoff, KnowledgeGap, Message, ToolCall


class CustomerConversationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, conversation_id: str) -> Conversation | None:
        return self.session.get(Conversation, conversation_id)

    def list_messages(self, conversation_id: str) -> list[Message]:
        statement: Select[tuple[Message]] = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(
                Message.created_at,
                case(
                    (Message.role == "customer", 0),
                    (Message.role == "assistant", 1),
                    (Message.role == "human_agent", 2),
                    else_=3,
                ),
                Message.id,
            )
        )
        return list(self.session.scalars(statement))

    def list_for_customer(self, customer_id: str) -> list[Conversation]:
        statement: Select[tuple[Conversation]] = (
            select(Conversation)
            .where(Conversation.customer_id == customer_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id)
        )
        return list(self.session.scalars(statement))

    def add_conversation(self, conversation: Conversation) -> None:
        self.session.add(conversation)

    def add_message(self, message: Message) -> None:
        self.session.add(message)

    def add_tool_call(self, tool_call: ToolCall) -> None:
        self.session.add(tool_call)

    def add_handoff(self, handoff: Handoff) -> None:
        self.session.add(handoff)

    def add_knowledge_gap(self, knowledge_gap: KnowledgeGap) -> None:
        self.session.add(knowledge_gap)
