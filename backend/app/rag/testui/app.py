"""用于临时知识更新和混合检索的最小 FastAPI 测试页面。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.rag.engine import RAGEngine

app = FastAPI(title="ServiceLoop RAG 中文测试页面", version="0.1.0")
engine = RAGEngine()
INDEX_HTML = Path(__file__).with_name("index.html")


class KnowledgeInput(BaseModel):
    document_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    source: str = Field(default="testui", max_length=100)


class SearchInput(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(INDEX_HTML)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "component": "rag-testui"}


@app.get("/api/status")
def status() -> dict:
    return engine.status()


@app.get("/api/documents")
def documents() -> list[dict]:
    return engine.list_documents()


@app.get("/api/documents/{document_id}/versions")
def document_versions(document_id: str) -> list[dict]:
    try:
        return engine.list_versions(document_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/documents")
def upsert_document(payload: KnowledgeInput) -> dict:
    try:
        return engine.upsert_document(
            document_id=payload.document_id,
            title=payload.title,
            content=payload.content,
            source=payload.source,
        )
    except (ImportError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/documents/{document_id}")
def archive_document(document_id: str) -> dict:
    try:
        return engine.archive_document(document_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/search")
def search(payload: SearchInput) -> dict:
    try:
        hits = engine.search(payload.query, limit=payload.limit)
    except (ImportError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "query": payload.query,
        "hits": hits,
        "message": "知识索引为空。" if not engine.status()["ready"] else None,
    }
