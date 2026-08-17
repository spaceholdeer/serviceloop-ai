"""确定性的订单查询服务。"""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy.orm import Session, sessionmaker

from app.repositories import BusinessRepository

DEFAULT_ORDERS = {
    "ORD-202608-1001": {
        "order_id": "ORD-202608-1001",
        "customer_id": "customer-demo-001",
        "product_name": "X3 Pro 智能手表",
        "status": "shipped",
        "paid_at": "2026-08-12T10:30:00+08:00",
        "shipped_at": "2026-08-13T16:20:00+08:00",
        "amount": 1299.0,
    },
    "ORD-202608-1002": {
        "order_id": "ORD-202608-1002",
        "customer_id": "customer-demo-001",
        "product_name": "X3 Pro 充电底座",
        "status": "processing",
        "paid_at": "2026-08-15T09:10:00+08:00",
        "shipped_at": None,
        "amount": 199.0,
    },
}


class OrderService:
    def __init__(
        self,
        orders: dict[str, dict] | None = None,
        *,
        session_factory: sessionmaker[Session] | None = None,
    ):
        self._orders = deepcopy(orders if orders is not None else DEFAULT_ORDERS)
        self._session_factory = session_factory

    def get_order(self, *, customer_id: str, order_id: str) -> dict:
        """查询属于当前客户的订单，不向其他客户泄露订单是否存在。"""

        clean_order_id = order_id.strip()
        if self._session_factory is not None:
            with self._session_factory() as session:
                record = BusinessRepository(session).get_order(clean_order_id, customer_id)
                order = (
                    {
                        "order_id": record.order_number,
                        "customer_id": record.customer_id,
                        "product_name": record.product_name,
                        "status": record.status,
                        "paid_at": record.paid_at.isoformat(),
                        "shipped_at": record.shipped_at.isoformat() if record.shipped_at else None,
                        "amount": float(record.amount),
                    }
                    if record
                    else None
                )
        else:
            order = self._orders.get(clean_order_id)
        if order is None or order["customer_id"] != customer_id:
            return {
                "ok": False,
                "data": None,
                "error_code": "order_not_found",
                "message": "未找到该客户的订单，请确认订单号。",
            }
        public_order = {key: value for key, value in order.items() if key != "customer_id"}
        return {"ok": True, "data": public_order, "error_code": None}
