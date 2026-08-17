"""写入可重复执行的知识运营演示数据。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.db.models import (
    Conversation,
    CustomerFeedback,
    CustomerOrder,
    Handoff,
    HumanResolution,
    KnowledgeGap,
    Message,
    Shipment,
    SupportTicket,
    ToolCall,
)
from app.db.session import transactional_session

DEMO_CASES = (
    {
        "suffix": "001",
        "question": "X3 智能手表未激活时可以在几天内退货？",
        "reply": "商品未激活且配件齐全时，请在签收后 7 天内申请退货。",
        "score": 0.18,
    },
    {
        "suffix": "002",
        "question": "X3 手表包装完整但已经拆封，退货条件是什么？",
        "reply": "拆封不等于激活；请先核对设备激活状态、配件和签收时间。",
        "score": 0.23,
    },
)


def seed_operations_demo() -> int:
    created = 0
    with transactional_session() as session:
        for item in DEMO_CASES:
            suffix = str(item["suffix"])
            gap_id = f"KGC-DEMO-{suffix}"
            if session.get(KnowledgeGap, gap_id) is not None:
                continue
            conversation_id = f"conversation-ops-demo-{suffix}"
            handoff_id = f"handoff-ops-demo-{suffix}"
            conversation = Conversation(
                id=conversation_id,
                customer_id=f"customer-demo-{suffix}",
                subject="X3 智能手表退货条件",
                status="resolved",
            )
            handoff = Handoff(
                id=handoff_id,
                conversation=conversation,
                reason_code="knowledge_insufficient",
                customer_question=str(item["question"]),
                agent_summary="现有知识未覆盖 X3 拆封、激活状态与退货时间的组合条件。",
                context_package={"product": "X3 智能手表", "demo": True},
                status="resolved",
                assigned_agent_id="agent-demo-001",
            )
            session.add_all(
                [
                    conversation,
                    handoff,
                    Message(
                        id=f"message-ops-demo-customer-{suffix}",
                        conversation=conversation,
                        role="customer",
                        source="customer",
                        content=str(item["question"]),
                    ),
                    Message(
                        id=f"message-ops-demo-human-{suffix}",
                        conversation=conversation,
                        role="human_agent",
                        source="agent-demo-001",
                        content=str(item["reply"]),
                    ),
                    HumanResolution(
                        id=f"resolution-ops-demo-{suffix}",
                        conversation=conversation,
                        handoff=handoff,
                        agent_id="agent-demo-001",
                        resolution_code="policy_explained",
                        action_taken="核对设备激活状态、配件完整度与签收时间",
                        reply_to_customer=str(item["reply"]),
                        internal_notes="ServiceLoop 固定演示数据",
                    ),
                    KnowledgeGap(
                        id=gap_id,
                        conversation_id=conversation_id,
                        question=str(item["question"]),
                        reason="low_knowledge_relevance",
                        evidence={
                            "demo": True,
                            "knowledge_searches": [
                                {
                                    "query": str(item["question"]),
                                    "hit_count": 1,
                                    "best_rerank_score": item["score"],
                                    "minimum_rerank_score": 0.35,
                                }
                            ],
                        },
                    ),
                ]
            )
            created += 1
        created += _seed_business_records(session)
        created += _seed_data_flywheel_signals(session)
    return created


def _seed_business_records(session) -> int:
    created = 0
    orders = (
        {
            "id": "business-order-demo-001",
            "order_number": "ORD-202608-1001",
            "product_name": "X3 Pro 智能手表",
            "status": "shipped",
            "amount": Decimal("1299.00"),
            "paid_at": "2026-08-12T10:30:00+08:00",
            "shipped_at": "2026-08-13T16:20:00+08:00",
        },
        {
            "id": "business-order-demo-002",
            "order_number": "ORD-202608-1002",
            "product_name": "X3 Pro 充电底座",
            "status": "processing",
            "amount": Decimal("199.00"),
            "paid_at": "2026-08-15T09:10:00+08:00",
            "shipped_at": None,
        },
    )
    for item in orders:
        exists = session.scalar(
            select(CustomerOrder).where(CustomerOrder.order_number == item["order_number"])
        )
        if exists:
            continue
        session.add(
            CustomerOrder(
                id=item["id"],
                order_number=item["order_number"],
                customer_id="customer-demo-001",
                product_name=item["product_name"],
                status=item["status"],
                amount=item["amount"],
                paid_at=datetime.fromisoformat(item["paid_at"]),
                shipped_at=(
                    datetime.fromisoformat(item["shipped_at"])
                    if item["shipped_at"]
                    else None
                ),
            )
        )
        created += 1
    session.flush()
    first_order = session.scalar(
        select(CustomerOrder).where(CustomerOrder.order_number == "ORD-202608-1001")
    )
    if first_order and session.get(Shipment, "shipment-demo-001") is None:
        session.add(
            Shipment(
                id="shipment-demo-001",
                order_id=first_order.id,
                carrier="顺丰速运",
                tracking_number="SF202608130001",
                status="in_transit",
                latest_event="快件已到达上海转运中心",
                latest_event_at=datetime.fromisoformat("2026-08-15T08:45:00+08:00"),
                estimated_delivery=datetime.fromisoformat("2026-08-16T18:00:00+08:00"),
            )
        )
        created += 1
    if session.get(SupportTicket, "ticket-demo-001") is None:
        session.add(
            SupportTicket(
                id="ticket-demo-001",
                ticket_number="TKT-DEMO-001",
                customer_id="customer-demo-001",
                conversation_id="conversation-ops-demo-001",
                category="after_sales",
                issue="核对 X3 智能手表激活状态与退货条件",
                status="resolved",
            )
        )
        created += 1
    return created


def _seed_data_flywheel_signals(session) -> int:
    created = 0
    if session.get(CustomerFeedback, "feedback-demo-001") is None:
        session.add(
            CustomerFeedback(
                id="feedback-demo-001",
                conversation_id="conversation-ops-demo-001",
                customer_id="customer-demo-001",
                rating=2,
                comment="最终解决了，但前面没有直接说明未激活和拆封的区别。",
            )
        )
        created += 1
    if session.get(ToolCall, "tool-call-demo-failed-001") is None:
        session.add(
            ToolCall(
                id="tool-call-demo-failed-001",
                conversation_id="conversation-ops-demo-002",
                service_name="logistics",
                operation="get_logistics",
                input_payload={"order_id": "ORD-202608-UNKNOWN"},
                output_payload=None,
                status="failed",
                latency_ms=128,
                error_message="演示信号：物流记录未同步。",
            )
        )
        created += 1
    return created


if __name__ == "__main__":
    count = seed_operations_demo()
    print(f"ServiceLoop operations demo records created: {count}.")
