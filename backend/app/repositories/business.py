"""订单、物流和工单的数据访问。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CustomerOrder, Shipment, SupportTicket


class BusinessRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_order(self, order_number: str, customer_id: str) -> CustomerOrder | None:
        return self.session.scalar(
            select(CustomerOrder).where(
                CustomerOrder.order_number == order_number,
                CustomerOrder.customer_id == customer_id,
            )
        )

    def get_shipment(self, order_number: str, customer_id: str) -> tuple[Shipment, CustomerOrder] | None:
        row = self.session.execute(
            select(Shipment, CustomerOrder)
            .join(CustomerOrder, Shipment.order_id == CustomerOrder.id)
            .where(
                CustomerOrder.order_number == order_number,
                CustomerOrder.customer_id == customer_id,
            )
        ).one_or_none()
        return (row[0], row[1]) if row else None

    def add_ticket(self, ticket: SupportTicket) -> None:
        self.session.add(ticket)

