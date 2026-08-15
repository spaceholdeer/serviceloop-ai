from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.customer import get_customer_service_agent
from app.db import Base, get_session
from app.db.models import Conversation, Handoff, Message, ToolCall
from app.main import app


class StubCustomerServiceAgent:
    def __init__(self, *, handoff_required: bool = False):
        self.handoff_required = handoff_required
        self.invocations: list[dict[str, Any]] = []

    def invoke(
        self,
        *,
        conversation_id: str,
        customer_id: str,
        message: str,
        history: Sequence[dict[str, str]] = (),
    ) -> dict:
        self.invocations.append(
            {
                "conversation_id": conversation_id,
                "customer_id": customer_id,
                "message": message,
                "history": list(history),
            }
        )
        if self.handoff_required:
            return {
                "final_answer": "已经为你转接人工客服。",
                "handoff_required": True,
                "handoff_reason": "refund_request",
                "handoff": {
                    "handoff_id": "HOF-API-001",
                    "agent_summary": "客户申请退款",
                    "context_package": {"risk": "refund"},
                },
                "tool_events": [],
            }
        return {
            "final_answer": "预计明天送达。",
            "handoff_required": False,
            "handoff_reason": None,
            "handoff": None,
            "tool_events": [
                {
                    "service_name": "get_logistics",
                    "input": {"order_id": "ORD-001"},
                    "result": {"ok": True, "data": {"eta": "tomorrow"}},
                    "status": "succeeded",
                }
            ],
        }


@pytest.fixture
def api_database() -> Iterator[sessionmaker[Session]]:
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
    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_customer_chat_creates_and_persists_complete_turn(api_database):
    agent = StubCustomerServiceAgent()
    app.dependency_overrides[get_customer_service_agent] = lambda: agent

    response = TestClient(app).post(
        "/api/customer/chat",
        json={
            "customer_id": "customer-demo-001",
            "message": "ORD-001 什么时候到？",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "预计明天送达。"
    assert body["conversation_status"] == "active"
    assert body["handoff_required"] is False
    assert body["customer_message_id"]
    assert body["assistant_message_id"]

    with api_database() as session:
        conversation = session.get(Conversation, body["conversation_id"])
        assert conversation is not None
        assert conversation.customer_id == "customer-demo-001"
        assert session.scalar(select(func.count(Message.id))) == 2
        tool_call = session.scalar(select(ToolCall))
        assert tool_call is not None
        assert tool_call.service_name == "logistics"
        assert tool_call.operation == "get_logistics"
        assert tool_call.status == "succeeded"


def test_next_turn_receives_persisted_history_and_history_api(api_database):
    agent = StubCustomerServiceAgent()
    app.dependency_overrides[get_customer_service_agent] = lambda: agent
    client = TestClient(app)

    first = client.post(
        "/api/customer/chat",
        json={"customer_id": "customer-demo-001", "message": "订单什么时候到？"},
    ).json()
    second_response = client.post(
        "/api/customer/chat",
        json={
            "conversation_id": first["conversation_id"],
            "customer_id": "customer-demo-001",
            "message": "那明天大约几点？",
        },
    )

    assert second_response.status_code == 200
    assert agent.invocations[1]["history"] == [
        {"role": "customer", "content": "订单什么时候到？"},
        {"role": "assistant", "content": "预计明天送达。"},
    ]

    history_response = client.get(
        f"/api/customer/conversations/{first['conversation_id']}/messages",
        params={"customer_id": "customer-demo-001"},
    )
    assert history_response.status_code == 200
    assert [item["role"] for item in history_response.json()] == [
        "customer",
        "assistant",
        "customer",
        "assistant",
    ]


def test_history_keeps_customer_before_answer_when_timestamps_are_equal(api_database):
    shared_time = datetime(2026, 8, 15, 10, 3, tzinfo=UTC)
    conversation = Conversation(
        id="conversation-same-time",
        customer_id="customer-demo-001",
        subject="退货条款",
    )
    with api_database() as session:
        session.add(conversation)
        session.add_all(
            [
                Message(
                    id="z-customer-message",
                    conversation_id=conversation.id,
                    role="customer",
                    source="customer",
                    content="X3 智能手表退货条款是什么？",
                    created_at=shared_time,
                ),
                Message(
                    id="a-assistant-message",
                    conversation_id=conversation.id,
                    role="assistant",
                    source="customer_service_agent",
                    content="根据条款，需要满足时间和商品状态条件。",
                    created_at=shared_time,
                ),
            ]
        )
        session.commit()

    response = TestClient(app).get(
        f"/api/customer/conversations/{conversation.id}/messages",
        params={"customer_id": "customer-demo-001"},
    )

    assert response.status_code == 200
    assert [item["role"] for item in response.json()] == ["customer", "assistant"]
    assert [item["content"] for item in response.json()] == [
        "X3 智能手表退货条款是什么？",
        "根据条款，需要满足时间和商品状态条件。",
    ]


def test_customer_can_create_and_read_conversation(api_database):
    agent = StubCustomerServiceAgent()
    app.dependency_overrides[get_customer_service_agent] = lambda: agent
    client = TestClient(app)

    created = client.post(
        "/api/customer/conversations",
        json={"customer_id": "customer-demo-001", "subject": "查询物流"},
    )

    assert created.status_code == 201
    conversation_id = created.json()["id"]
    loaded = client.get(
        f"/api/customer/conversations/{conversation_id}",
        params={"customer_id": "customer-demo-001"},
    )
    assert loaded.status_code == 200
    assert loaded.json()["subject"] == "查询物流"

    hidden_from_other_customer = client.get(
        f"/api/customer/conversations/{conversation_id}",
        params={"customer_id": "another-customer"},
    )
    assert hidden_from_other_customer.status_code == 404

    listed = client.get(
        "/api/customer/conversations",
        params={"customer_id": "customer-demo-001"},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [conversation_id]


def test_handoff_is_persisted_and_stops_further_agent_replies(api_database):
    agent = StubCustomerServiceAgent(handoff_required=True)
    app.dependency_overrides[get_customer_service_agent] = lambda: agent
    client = TestClient(app)

    first = client.post(
        "/api/customer/chat",
        json={"customer_id": "customer-demo-001", "message": "我要退款"},
    )

    assert first.status_code == 200
    body = first.json()
    assert body["handoff_required"] is True
    assert body["conversation_status"] == "waiting_for_human"

    with api_database() as session:
        handoff = session.scalar(select(Handoff))
        assert handoff is not None
        assert handoff.id == "HOF-API-001"
        assert handoff.reason_code == "refund_request"
        assert handoff.status == "queued"

    second = client.post(
        "/api/customer/chat",
        json={
            "conversation_id": body["conversation_id"],
            "customer_id": "customer-demo-001",
            "message": "还有人在吗？",
        },
    )
    assert second.status_code == 409
    assert len(agent.invocations) == 1
