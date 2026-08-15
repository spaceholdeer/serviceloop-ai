from fastapi.testclient import TestClient

from app.rag.testui.app import app


def test_testui_starts_without_knowledge_or_model_credentials():
    client = TestClient(app)

    page = client.get("/")
    status = client.get("/api/status")
    search = client.post("/api/search", json={"query": "退款", "limit": 5})

    assert page.status_code == 200
    assert "ServiceLoop RAG 中文测试页面" in page.text
    assert status.json()["ready"] is False
    assert search.json()["hits"] == []


def test_testui_accepts_a_pure_english_query():
    response = TestClient(app).post(
        "/api/search", json={"query": "refund policy", "limit": 5}
    )

    assert response.status_code == 200
    assert response.json()["hits"] == []
