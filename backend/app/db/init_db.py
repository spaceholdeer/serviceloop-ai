"""创建简历演示项目需要的 MySQL 表。"""

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_engine


def init_database() -> None:
    Base.metadata.create_all(bind=get_engine())


if __name__ == "__main__":
    init_database()
    print("ServiceLoop MySQL tables are ready.")
