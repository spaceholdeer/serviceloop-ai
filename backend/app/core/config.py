"""ServiceLoop 后端配置。

数据库连接信息只从仓库根目录 ``.env`` 读取，避免本地、测试和演示环境出现多套来源。
"""

from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


def get_database_url(env_file: Path = ENV_FILE) -> str:
    """只从根目录 ``.env`` 读取一个 MySQL 连接地址。"""

    value = dotenv_values(env_file, interpolate=False).get("DATABASE_URL")
    database_url = str(value or "").strip()
    if not database_url:
        raise RuntimeError("根目录 .env 缺少 DATABASE_URL。")
    if not database_url.startswith("mysql+pymysql://"):
        raise RuntimeError("DATABASE_URL 必须使用 mysql+pymysql 驱动。")
    return database_url


def get_deepseek_settings(env_file: Path = ENV_FILE) -> tuple[str, str]:
    """读取 DeepSeek API Key 和模型名，不回退到系统环境变量。"""

    values = dotenv_values(env_file, interpolate=False)
    api_key = str(values.get("DEEPSEEK_API_KEY") or "").strip()
    model = str(values.get("DEEPSEEK_MODEL") or "deepseek-v4-flash").strip()
    if not api_key:
        raise RuntimeError("根目录 .env 缺少 DEEPSEEK_API_KEY。")
    return api_key, model
