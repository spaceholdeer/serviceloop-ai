from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.customer_service import CustomerServiceDependencies
from app.api.customer import get_customer_service_dependencies
from app.db import Base, get_session
from app.db.models import (
    Conversation,
    HumanResolution,
    KnowledgeDocument,
    KnowledgeDraft,
    KnowledgeGap,
)
from app.main import app


class StubKnowledgeService:
    def __init__(self):
        self.documents: list[dict] = []
        self.index_version = 0

    def replace_all(self, documents: list[dict]) -> dict:
        self.documents = [dict(item) for item in documents]
        self.index_version += 1
        return {
            "document_count": len(documents),
            "chunk_count": len(documents),
            "index_version": self.index_version,
        }

    def status(self) -> dict:
        return {
            "document_count": len(self.documents),
            "chunk_count": len(self.documents),
            "index_version": self.index_version,
            "ready": bool(self.documents),
        }


@pytest.fixture
def operations_api() -> Iterator[tuple[TestClient, sessionmaker[Session], StubKnowledgeService]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    knowledge = StubKnowledgeService()
    dependencies = CustomerServiceDependencies(knowledge=knowledge)  # type: ignore[arg-type]

    def override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_customer_service_dependencies] = lambda: dependencies
    try:
        yield TestClient(app), factory, knowledge
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _seed_gap(factory: sessionmaker[Session]) -> str:
    conversation = Conversation(
        id="conversation-gap-001",
        customer_id="customer-demo-001",
        subject="X3 特殊退货条款",
        status="resolved",
    )
    resolution = HumanResolution(
        id="resolution-gap-001",
        conversation=conversation,
        handoff_id="handoff-placeholder",
        agent_id="agent-demo-001",
        resolution_code="policy_explained",
        action_taken="核对商品状态与购买时间",
        reply_to_customer="商品未激活且配件齐全时，请在签收后 7 天内申请。",
    )
    gap = KnowledgeGap(
        id="KGC-API-001",
        conversation=conversation,
        question="X3 智能手表的特殊退货条件是什么？",
        reason="low_knowledge_relevance",
        evidence={"best_rerank_score": 0.2},
    )
    with factory() as session:
        session.add_all([conversation, resolution, gap])
        session.commit()
    return gap.id


def test_operations_agent_creates_editable_draft_and_publishes(
    operations_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory, knowledge = operations_api
    gap_id = _seed_gap(factory)

    def unavailable_model():
        raise RuntimeError("model unavailable in test")

    monkeypatch.setattr(
        "app.agents.knowledge_operations.create_deepseek_chat_model", unavailable_model
    )

    gaps = client.get("/api/operations/knowledge-gaps")
    assert gaps.status_code == 200
    assert gaps.json()[0]["human_resolution"]["resolution_code"] == "policy_explained"

    generated = client.post(
        "/api/operations/knowledge-agent/run",
        json={"gap_ids": [gap_id], "operator_id": "operations-demo-001"},
    )
    assert generated.status_code == 201
    assert generated.json()["processed_gap_count"] == 1
    draft_id = generated.json()["drafts"][0]["id"]

    edited = client.patch(
        f"/api/operations/knowledge-drafts/{draft_id}",
        json={
            "title": "X3 智能手表退货条件",
            "content": "未激活且配件齐全的商品，可在签收后 7 天内申请退货。",
        },
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "X3 智能手表退货条件"

    published = client.post(
        f"/api/operations/knowledge-drafts/{draft_id}/publish",
        json={"operator_id": "operations-demo-001"},
    )
    assert published.status_code == 200
    document_id = published.json()["document"]["id"]
    assert published.json()["draft"]["status"] == "published"
    assert knowledge.documents[0]["id"] == document_id

    with factory() as session:
        gap = session.get(KnowledgeGap, gap_id)
        draft = session.get(KnowledgeDraft, draft_id)
        document = session.get(KnowledgeDocument, document_id)
        assert gap is not None and gap.status == "resolved"
        assert draft is not None and draft.status == "published"
        assert document is not None and document.current_version == 1


def test_direct_document_update_versions_and_archive(operations_api) -> None:
    client, _, knowledge = operations_api
    created = client.post(
        "/api/operations/knowledge-documents",
        json={"title": "物流说明", "content": "发货后可查询物流轨迹。"},
    )
    assert created.status_code == 201
    document_id = created.json()["id"]

    updated = client.put(
        f"/api/operations/knowledge-documents/{document_id}",
        json={"title": "物流说明", "content": "发货后可查询承运商与物流轨迹。"},
    )
    assert updated.status_code == 200
    assert updated.json()["current_version"] == 2

    versions = client.get(f"/api/operations/knowledge-documents/{document_id}/versions")
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [2, 1]

    archived = client.delete(f"/api/operations/knowledge-documents/{document_id}")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert knowledge.documents == []


def test_operations_overview_reports_persisted_state(operations_api) -> None:
    client, factory, _ = operations_api
    _seed_gap(factory)

    overview = client.get("/api/operations/overview")
    assert overview.status_code == 200
    assert overview.json()["pending_gaps"] == 1
    assert overview.json()["published_documents"] == 0
    assert overview.json()["index"]["storage"] == "mysql_backed_runtime_index"
