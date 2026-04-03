"""Tests for persistent config and setup wizard."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from memorychain_cli import settings
from memorychain_cli.setup import validate_openai_key


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect config to a temp directory."""
    config_dir = tmp_path / ".memorychain"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(settings, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(settings, "CONFIG_FILE", config_file)
    return config_file


class TestSettings:
    def test_load_empty(self, tmp_config: Path) -> None:
        assert settings.load_config() == {}

    def test_save_and_load(self, tmp_config: Path) -> None:
        settings.save_config({"openai_api_key": "sk-test123", "llm_provider": "openai"})
        config = settings.load_config()
        assert config["openai_api_key"] == "sk-test123"
        assert config["llm_provider"] == "openai"

    def test_is_configured_false(self, tmp_config: Path) -> None:
        assert settings.is_configured() is False

    def test_is_configured_true(self, tmp_config: Path) -> None:
        settings.save_config({"openai_api_key": "sk-test"})
        assert settings.is_configured() is True

    def test_put_and_get(self, tmp_config: Path) -> None:
        settings.put("user_id", "my-user")
        assert settings.get("user_id") == "my-user"
        assert settings.get("nonexistent", "default") == "default"

    def test_get_openai_key_from_config(self, tmp_config: Path) -> None:
        settings.save_config({"openai_api_key": "sk-from-config"})
        assert settings.get_openai_key() == "sk-from-config"

    def test_get_openai_key_from_env(self, tmp_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        assert settings.get_openai_key() == "sk-from-env"

    def test_config_file_created_on_save(self, tmp_config: Path) -> None:
        assert not tmp_config.exists()
        settings.save_config({"test": "value"})
        assert tmp_config.exists()
        data = json.loads(tmp_config.read_text())
        assert data["test"] == "value"


class TestValidateKey:
    def test_valid_key(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "object": "user",
            "name": "Test User",
            "email": "test@example.com",
            "orgs": {"data": [{"title": "My Org"}]},
        }
        with patch("memorychain_cli.setup.httpx.get", return_value=mock_resp):
            result = validate_openai_key("sk-test")
            assert result is not None
            assert result["name"] == "Test User"

    def test_invalid_key(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("memorychain_cli.setup.httpx.get", return_value=mock_resp):
            result = validate_openai_key("sk-bad")
            assert result is None

    def test_connection_error(self) -> None:
        import httpx as _httpx
        with patch("memorychain_cli.setup.httpx.get", side_effect=_httpx.ConnectError("refused")):
            result = validate_openai_key("sk-test")
            assert result is None
