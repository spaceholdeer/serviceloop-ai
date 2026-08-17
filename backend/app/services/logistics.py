"""确定性的物流查询服务。"""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy.orm import Session, sessionmaker

from app.repositories import BusinessRepository

DEFAULT_LOGISTICS = {
    "ORD-202608-1001": {
        "order_id": "ORD-202608-1001",
        "customer_id": "customer-demo-001",
        "carrier": "顺丰速运",
        "tracking_number": "SF202608130001",
        "status": "in_transit",
        "latest_event": "快件已到达上海转运中心",
        "latest_event_at": "2026-08-15T08:45:00+08:00",
        "estimated_delivery": "2026-08-16",
    }
}


class LogisticsService:
    def __init__(
        self,
        shipments: dict[str, dict] | None = None,
        *,
        session_factory: sessionmaker[Session] | None = None,
    ):
        self._shipments = deepcopy(shipments if shipments is not None else DEFAULT_LOGISTICS)
        self._session_factory = session_factory

    def get_logistics(self, *, customer_id: str, order_id: str) -> dict:
        clean_order_id = order_id.strip()
        if self._session_factory is not None:
            with self._session_factory() as session:
                row = BusinessRepository(session).get_shipment(clean_order_id, customer_id)
                if row:
                    record, order = row
                    shipment = {
                        "order_id": order.order_number,
                        "customer_id": order.customer_id,
                        "carrier": record.carrier,
                        "tracking_number": record.tracking_number,
                        "status": record.status,
                        "latest_event": record.latest_event,
                        "latest_event_at": record.latest_event_at.isoformat(),
                        "estimated_delivery": (
                            record.estimated_delivery.date().isoformat()
                            if record.estimated_delivery
                            else None
                        ),
                    }
                else:
                    shipment = None
        else:
            shipment = self._shipments.get(clean_order_id)
        if shipment is None or shipment["customer_id"] != customer_id:
            return {
                "ok": False,
                "data": None,
                "error_code": "logistics_not_found",
                "message": "该订单暂时没有可查询的物流记录。",
            }
        public_shipment = {
            key: value for key, value in shipment.items() if key != "customer_id"
        }
        return {"ok": True, "data": public_shipment, "error_code": None}
