"""内部 ``app.rag`` 模块面向业务层的调用边界。

数据库持久化和运营人员身份将在数据中台阶段补充。RAG 测试页面是隔离的开发入口，
因此可以直接调用 RAG 引擎。
"""

from __future__ import annotations

from app.rag import RAGEngine


class KnowledgeService:
    def __init__(self, engine: RAGEngine | None = None):
        self.engine = engine or RAGEngine()

    def search(self, query: str, limit: int = 8) -> list[dict]:
        return self.engine.search(query, limit=limit)

    def upsert(self, **knowledge) -> dict:
        return self.engine.upsert_document(**knowledge)

    def archive(self, document_id: str) -> dict:
        return self.engine.archive_document(document_id)

    def replace_all(self, documents: list[dict]) -> dict:
        return self.engine.replace_documents(documents)

    def status(self) -> dict:
        return self.engine.status()
