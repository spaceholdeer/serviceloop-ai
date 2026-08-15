"""数据库配置测试。"""

from pathlib import Path

import pytest

from app.core.config import get_database_url, get_deepseek_settings


def write_env(path: Path, **values: str) -> None:
    path.write_text(
        "\n".join(f"{name}={value}" for name, value in values.items()) + "\n",
        encoding="utf-8",
    )


def test_database_config_only_reads_the_repository_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    write_env(
        env_file,
        DATABASE_URL="mysql+pymysql://app_user:file-secret@mysql:3306/serviceloop",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://app_user:process-secret@mysql:3306/serviceloop",
    )

    assert get_database_url(env_file) == (
        "mysql+pymysql://app_user:file-secret@mysql:3306/serviceloop"
    )


def test_database_config_reports_missing_values(tmp_path):
    env_file = tmp_path / ".env"
    write_env(env_file, UNUSED="value")

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_database_url(env_file)


def test_database_config_rejects_non_mysql_urls(tmp_path):
    env_file = tmp_path / ".env"
    write_env(env_file, DATABASE_URL="sqlite:///serviceloop.db")

    with pytest.raises(RuntimeError, match=r"mysql\+pymysql"):
        get_database_url(env_file)


def test_deepseek_settings_only_read_the_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    write_env(
        env_file,
        DEEPSEEK_API_KEY="file-key",
        DEEPSEEK_MODEL="deepseek-v4-flash",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "process-key")

    assert get_deepseek_settings(env_file) == ("file-key", "deepseek-v4-flash")
