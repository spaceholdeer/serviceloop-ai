"""确定性的物流查询服务。"""

from __future__ import annotations

from copy import deepcopy

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
    def __init__(self, shipments: dict[str, dict] | None = None):
        self._shipments = deepcopy(shipments if shipments is not None else DEFAULT_LOGISTICS)

    def get_logistics(self, *, customer_id: str, order_id: str) -> dict:
        shipment = self._shipments.get(order_id.strip())
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
