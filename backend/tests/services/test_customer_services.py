from app.services.logistics import LogisticsService
from app.services.order import OrderService
from app.services.ticket import TicketService


def test_order_service_only_returns_the_current_customers_order():
    service = OrderService()

    own_order = service.get_order(
        customer_id="customer-demo-001", order_id="ORD-202608-1001"
    )
    another_customer = service.get_order(
        customer_id="customer-demo-002", order_id="ORD-202608-1001"
    )

    assert own_order["ok"] is True
    assert "customer_id" not in own_order["data"]
    assert another_customer["error_code"] == "order_not_found"


def test_logistics_service_returns_structured_tracking_data():
    result = LogisticsService().get_logistics(
        customer_id="customer-demo-001", order_id="ORD-202608-1001"
    )

    assert result["ok"] is True
    assert result["data"]["status"] == "in_transit"
    assert result["data"]["estimated_delivery"] == "2026-08-16"


def test_ticket_service_creates_an_open_ticket():
    service = TicketService()

    result = service.create_ticket(
        customer_id="customer-demo-001",
        conversation_id="conversation-001",
        issue="需要更换损坏的商品",
        category="after_sales",
    )

    assert result["ok"] is True
    assert result["data"]["status"] == "open"
    assert len(service.tickets) == 1
