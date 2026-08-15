from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.db.models import Conversation, Handoff, HumanResolution, Message
from app.main import app


def _database() -> tuple[sessionmaker[Session], TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return factory, TestClient(app)


def _seed(factory: sessionmaker[Session]) -> tuple[str, str]:
    conversation = Conversation(
        id="conversation-agent-001",
        customer_id="customer-demo-001",
        subject="X3 Pro 退款申请",
        status="waiting_for_human",
    )
    handoff = Handoff(
        id="HOF-AGENT-001",
        conversation=conversation,
        reason_code="refund_request",
        customer_question="X3 Pro 有质量问题，我要退款",
        agent_summary="客户反馈购买 9 天的 X3 Pro 出现质量问题并明确申请退款。",
        context_package={"order_id": "ORD-202608-1001", "risk": "refund"},
        status="queued",
    )
    message = Message(
        id="message-agent-001",
        conversation=conversation,
        role="customer",
        source="customer",
        content="X3 Pro 有质量问题，我要退款",
    )
    with factory() as session:
        session.add_all([conversation, handoff, message])
        session.commit()
    return conversation.id, handoff.id


def test_agent_can_accept_reply_and_resolve_handoff() -> None:
    factory, client = _database()
    conversation_id, handoff_id = _seed(factory)
    try:
        queue = client.get("/api/agent/handoffs", params={"status": "queued"})
        assert queue.status_code == 200
        assert queue.json()[0]["id"] == handoff_id
        assert queue.json()[0]["customer_id"] == "customer-demo-001"

        accepted = client.post(
            f"/api/agent/handoffs/{handoff_id}/accept",
            json={"agent_id": "agent-demo-001"},
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "active"

        replied = client.post(
            f"/api/agent/handoffs/{handoff_id}/messages",
            json={"agent_id": "agent-demo-001", "content": "您好，我来继续处理退款申请。"},
        )
        assert replied.status_code == 200
        assert replied.json()["role"] == "human_agent"

        customer_reply = client.post(
            f"/api/customer/conversations/{conversation_id}/messages",
            json={"customer_id": "customer-demo-001", "content": "好的，包装还在。"},
        )
        assert customer_reply.status_code == 200
        assert customer_reply.json()["role"] == "customer"

        resolved = client.post(
            f"/api/agent/handoffs/{handoff_id}/resolve",
            json={
                "agent_id": "agent-demo-001",
                "resolution_code": "refund_submitted",
                "action_taken": "核对订单后提交退款申请",
                "reply_to_customer": "退款申请已提交，预计 1—3 个工作日原路退回。",
                "internal_notes": "演示处理记录",
            },
        )
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"

        with factory() as session:
            conversation = session.get(Conversation, conversation_id)
            handoff = session.get(Handoff, handoff_id)
            resolution = session.scalar(select(HumanResolution))
            assert conversation is not None and conversation.status == "resolved"
            assert handoff is not None and handoff.status == "resolved"
            assert resolution is not None
            assert resolution.resolution_code == "refund_submitted"
    finally:
        app.dependency_overrides.clear()


def test_handoff_cannot_be_reassigned_to_another_agent() -> None:
    factory, client = _database()
    _, handoff_id = _seed(factory)
    try:
        first = client.post(
            f"/api/agent/handoffs/{handoff_id}/accept",
            json={"agent_id": "agent-demo-001"},
        )
        second = client.post(
            f"/api/agent/handoffs/{handoff_id}/accept",
            json={"agent_id": "agent-demo-002"},
        )
        assert first.status_code == 200
        assert second.status_code == 409
    finally:
        app.dependency_overrides.clear()
