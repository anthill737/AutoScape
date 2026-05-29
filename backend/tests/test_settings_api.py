import os

import pytest
from fastapi.testclient import TestClient

from app import bootstrap
from app.api import settings as settings_api
from app.main import app


@pytest.fixture
def secrets_dir(tmp_path, monkeypatch):
    directory = tmp_path / "secrets"
    directory.mkdir()
    monkeypatch.setattr(bootstrap, "_SECRETS_DIR", directory)
    for name in bootstrap.REQUIRED_API_KEYS:
        monkeypatch.delenv(name, raising=False)
    yield directory


@pytest.fixture
def client(secrets_dir):
    with TestClient(app) as test_client:
        yield test_client


def test_get_keys_returns_masked_shape_without_raw_values(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-1234abcd")

    response = client.get("/api/settings/keys")

    assert response.status_code == 200
    body = response.json()
    assert [entry["name"] for entry in body] == list(bootstrap.REQUIRED_API_KEYS)
    anthropic = next(entry for entry in body if entry["name"] == "ANTHROPIC_API_KEY")
    assert anthropic == {
        "name": "ANTHROPIC_API_KEY",
        "set": True,
        "masked_value": "sk-t...abcd",
    }
    unset = [entry for entry in body if entry["name"] != "ANTHROPIC_API_KEY"]
    assert all(entry["set"] is False and entry["masked_value"] is None for entry in unset)
    assert "sk-test-1234abcd" not in response.text


def test_put_writes_secret_file_updates_masked_get_and_invokes_reload(
    client, secrets_dir, monkeypatch
):
    calls: list[tuple[str, ...] | None] = []
    original_reload = settings_api.reload_key_cache

    def spy_reload(names=None):
        calls.append(tuple(names) if names is not None else None)
        return original_reload(names)

    monkeypatch.setattr(settings_api, "reload_key_cache", spy_reload)

    response = client.put(
        "/api/settings/keys/ANTHROPIC_API_KEY",
        json={"value": "sk-test-1234abcd"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "ANTHROPIC_API_KEY",
        "set": True,
        "masked_value": "sk-t...abcd",
    }
    assert (secrets_dir / "ANTHROPIC_API_KEY").read_text(encoding="utf-8") == "sk-test-1234abcd"
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test-1234abcd"
    assert calls == [("ANTHROPIC_API_KEY",)]

    get_response = client.get("/api/settings/keys")
    anthropic = next(
        entry for entry in get_response.json() if entry["name"] == "ANTHROPIC_API_KEY"
    )
    assert anthropic["masked_value"] == "sk-t...abcd"


def test_delete_removes_secret_file_clears_cache_and_invokes_reload(
    client, secrets_dir, monkeypatch
):
    secret_file = secrets_dir / "ANTHROPIC_API_KEY"
    secret_file.write_text("sk-test-1234abcd", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-1234abcd")
    calls: list[tuple[str, ...] | None] = []
    original_reload = settings_api.reload_key_cache

    def spy_reload(names=None):
        calls.append(tuple(names) if names is not None else None)
        return original_reload(names)

    monkeypatch.setattr(settings_api, "reload_key_cache", spy_reload)

    response = client.delete("/api/settings/keys/ANTHROPIC_API_KEY")

    assert response.status_code == 200
    assert response.json()["set"] is False
    assert not secret_file.exists()
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert calls == [("ANTHROPIC_API_KEY",)]

    get_response = client.get("/api/settings/keys")
    anthropic = next(
        entry for entry in get_response.json() if entry["name"] == "ANTHROPIC_API_KEY"
    )
    assert anthropic == {
        "name": "ANTHROPIC_API_KEY",
        "set": False,
        "masked_value": None,
    }


def test_provider_test_returns_ok_and_verbatim_error(client, monkeypatch):
    async def ok_tester(api_key: str) -> None:
        assert api_key == "sk-valid"

    async def failing_tester(api_key: str) -> None:
        raise RuntimeError("provider said no")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-valid")
    monkeypatch.setitem(settings_api._PROVIDER_TESTERS, "OPENAI_API_KEY", ok_tester)
    ok_response = client.post("/api/settings/keys/OPENAI_API_KEY/test")
    assert ok_response.status_code == 200
    assert ok_response.json() == {"ok": True}

    monkeypatch.setitem(settings_api._PROVIDER_TESTERS, "OPENAI_API_KEY", failing_tester)
    error_response = client.post("/api/settings/keys/OPENAI_API_KEY/test")
    assert error_response.status_code == 200
    assert error_response.json() == {"ok": False, "error": "provider said no"}
