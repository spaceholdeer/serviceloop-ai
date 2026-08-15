from fastapi.testclient import TestClient

from app.agents.customer_service import CustomerServiceDependencies
from app.api.customer import get_customer_service_dependencies
from app.main import app


def test_operations_lists_pending_knowledge_gap_candidates():
    dependencies = CustomerServiceDependencies()
    dependencies.data.record_knowledge_gap_assessment(
        conversation_id="conversation-gap-001",
        customer_question="特殊售后规则是什么？",
        handoff_reason="low_knowledge_relevance",
        is_knowledge_gap=True,
        evidence={"best_rerank_score": 0.2},
    )
    app.dependency_overrides[get_customer_service_dependencies] = lambda: dependencies
    try:
        response = TestClient(app).get("/api/operations/knowledge-gaps")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "pending"
    assert response.json()[0]["reason"] == "low_knowledge_relevance"
