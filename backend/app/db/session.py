"""MySQL Engine 和请求级数据库会话。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(get_database_url())


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine or get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def get_session() -> Iterator[Session]:
    """供 FastAPI ``Depends`` 使用的请求级 Session。"""

    session = create_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transactional_session(
    factory: sessionmaker[Session] | None = None,
) -> Iterator[Session]:
    """提交一组写操作；发生异常时回滚。"""

    session = (factory or create_session_factory())()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
