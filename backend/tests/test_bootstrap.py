import importlib
import os
from pathlib import Path

from app import bootstrap


def test_load_startup_secrets_uses_existing_env_then_backend_env_then_secret_files(
    tmp_path, monkeypatch
):
    backend_env = tmp_path / "backend" / ".env.local"
    secrets_dir = tmp_path / "secrets"
    backend_env.parent.mkdir()
    secrets_dir.mkdir()
    backend_env.write_text(
        "GOOGLE_API_KEY=backend-google\n"
        "OPENAI_API_KEY=backend-openai\n",
        encoding="utf-8",
    )
    (secrets_dir / "GOOGLE_API_KEY").write_text("secret-google\n", encoding="utf-8")
    (secrets_dir / "OPENAI_API_KEY").write_text("secret-openai\n", encoding="utf-8")
    (secrets_dir / "ANTHROPIC_API_KEY").write_text("secret-anthropic\n", encoding="utf-8")
    (secrets_dir / "PERPLEXITY_API_KEY").write_text("secret-perplexity\n", encoding="utf-8")

    for name in bootstrap.REQUIRED_API_KEYS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "existing-google")
    monkeypatch.setattr(bootstrap, "_BACKEND_ENV_LOCAL", backend_env)
    monkeypatch.setattr(bootstrap, "_SECRETS_DIR", secrets_dir)

    found_files = bootstrap.load_startup_secrets()

    assert found_files == list(bootstrap.REQUIRED_API_KEYS)
    assert os.environ["GOOGLE_API_KEY"] == "existing-google"
    assert os.environ["OPENAI_API_KEY"] == "backend-openai"
    assert os.environ["ANTHROPIC_API_KEY"] == "secret-anthropic"
    assert os.environ["PERPLEXITY_API_KEY"] == "secret-perplexity"


def test_load_startup_secrets_allows_missing_backend_env_local(tmp_path, monkeypatch, caplog):
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    for name in bootstrap.REQUIRED_API_KEYS:
        monkeypatch.delenv(name, raising=False)
        (secrets_dir / name).write_text(f"{name.lower()}-secret\n", encoding="utf-8")

    monkeypatch.setattr(bootstrap, "_BACKEND_ENV_LOCAL", tmp_path / "backend" / ".env.local")
    monkeypatch.setattr(bootstrap, "_SECRETS_DIR", secrets_dir)

    bootstrap.load_startup_secrets()

    assert all(os.environ.get(name) for name in bootstrap.REQUIRED_API_KEYS)
    assert not [record for record in caplog.records if record.levelname in {"WARNING", "ERROR"}]


def test_load_startup_secrets_treats_empty_env_as_missing(tmp_path, monkeypatch):
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    for name in bootstrap.REQUIRED_API_KEYS:
        monkeypatch.delenv(name, raising=False)
        (secrets_dir / name).write_text(f"{name.lower()}-secret\n", encoding="utf-8")

    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setattr(bootstrap, "_BACKEND_ENV_LOCAL", tmp_path / "backend" / ".env.local")
    monkeypatch.setattr(bootstrap, "_SECRETS_DIR", secrets_dir)

    bootstrap.load_startup_secrets()

    assert os.environ["GOOGLE_API_KEY"] == "google_api_key-secret"


def test_main_loads_secrets_before_provider_imports():
    main_path = Path(importlib.import_module("app.main").__file__)
    source = main_path.read_text(encoding="utf-8")

    assert source.index("from app.bootstrap import") < source.index("from app.providers.")
