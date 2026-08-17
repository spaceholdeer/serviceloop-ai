from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.db.models import Conversation, CustomerOrder, Shipment, SupportTicket
from app.services.logistics import LogisticsService
from app.services.order import OrderService
from app.services.ticket import TicketService


def _factory() -> tuple[sessionmaker[Session], object]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def test_business_services_read_and_write_persisted_records():
    factory, engine = _factory()
    conversation = Conversation(
        id="conversation-business-001", customer_id="customer-demo-001"
    )
    order = CustomerOrder(
        id="order-business-001",
        order_number="ORD-DB-001",
        customer_id="customer-demo-001",
        product_name="X3 智能手表",
        status="shipped",
        amount=Decimal("1299.00"),
        paid_at=datetime(2026, 8, 12, tzinfo=UTC),
    )
    with factory() as session:
        session.add_all([conversation, order])
        session.flush()
        session.add(
            Shipment(
                order_id=order.id,
                carrier="顺丰速运",
                tracking_number="SF-DB-001",
                status="in_transit",
                latest_event="已到达转运中心",
                latest_event_at=datetime(2026, 8, 15, tzinfo=UTC),
            )
        )
        session.commit()

    order_result = OrderService(session_factory=factory).get_order(
        customer_id="customer-demo-001", order_id="ORD-DB-001"
    )
    logistics_result = LogisticsService(session_factory=factory).get_logistics(
        customer_id="customer-demo-001", order_id="ORD-DB-001"
    )
    ticket_result = TicketService(session_factory=factory).create_ticket(
        customer_id="customer-demo-001",
        conversation_id=conversation.id,
        issue="需要进一步检查设备",
        category="after_sales",
    )

    assert order_result["ok"] is True
    assert order_result["data"]["amount"] == 1299.0
    assert logistics_result["ok"] is True
    assert logistics_result["data"]["carrier"] == "顺丰速运"
    assert ticket_result["ok"] is True
    with factory() as session:
        assert session.query(SupportTicket).count() == 1
    Base.metadata.drop_all(engine)
    engine.dispose()
