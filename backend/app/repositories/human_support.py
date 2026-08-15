"""人工客服工作台的数据访问。"""

from __future__ import annotations

from sqlalchemy import Select, case, select
from sqlalchemy.orm import Session

from app.db.models import Handoff, HumanResolution, Message


class HumanSupportRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_handoff(self, handoff_id: str) -> Handoff | None:
        return self.session.get(Handoff, handoff_id)

    def list_handoffs(self, statuses: list[str] | None = None) -> list[Handoff]:
        statement: Select[tuple[Handoff]] = select(Handoff)
        if statuses:
            statement = statement.where(Handoff.status.in_(statuses))
        statement = statement.order_by(Handoff.requested_at.asc(), Handoff.id)
        return list(self.session.scalars(statement))

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

    def add_message(self, message: Message) -> None:
        self.session.add(message)

    def add_resolution(self, resolution: HumanResolution) -> None:
        self.session.add(resolution)
