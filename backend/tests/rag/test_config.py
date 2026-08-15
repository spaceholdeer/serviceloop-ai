from app.rag import config


def test_api_key_only_reads_repository_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DASHSCOPE_API_KEY=file-secret\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "process-secret")

    assert config.read_api_key("DASHSCOPE_API_KEY") == "file-secret"


def test_api_key_ignores_process_environment_when_env_file_is_missing(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "不存在的.env")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "process-secret")

    assert config.read_api_key("DASHSCOPE_API_KEY") is None
