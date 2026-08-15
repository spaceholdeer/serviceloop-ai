"""后端和独立测试页面共用的 RAG 运行配置。"""

from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"
_API_KEYS = {"DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY"}


def read_api_key(name: str) -> str | None:
    """只从仓库根目录的 ``.env`` 文件读取支持的 API 密钥。

    系统环境变量中的同名值会被忽略，所有密钥保持单一读取来源。
    """

    if name not in _API_KEYS:
        raise ValueError(f"不支持的 API 密钥名称：{name}")
    file_value = dotenv_values(ENV_FILE, interpolate=False).get(name)
    if not isinstance(file_value, str) or not file_value.strip():
        return None
    return file_value.strip()
