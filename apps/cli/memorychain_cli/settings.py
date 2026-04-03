"""Persistent configuration — stored in ~/.memorychain/config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".memorychain"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load config from disk. Returns empty dict if no config exists."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict[str, Any]) -> None:
    """Write config to disk."""
    _ensure_dir()
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )


def get(key: str, default: str = "") -> str:
    """Read a single config value."""
    return load_config().get(key, default)


def put(key: str, value: str) -> None:
    """Write a single config value."""
    config = load_config()
    config[key] = value
    save_config(config)


def is_configured() -> bool:
    """Check if the minimum required config exists."""
    config = load_config()
    return bool(config.get("openai_api_key"))


def get_openai_key() -> str | None:
    """Get OpenAI API key from config, falling back to env var."""
    return load_config().get("openai_api_key") or os.getenv("OPENAI_API_KEY")


def get_api_url() -> str:
    """Get the MemoryChain API URL."""
    return load_config().get("api_url", os.getenv("MEMORYCHAIN_API_URL", "http://localhost:8000"))


def get_api_key() -> str:
    """Get the MemoryChain internal API key."""
    return load_config().get("api_key", os.getenv("MEMORYCHAIN_API_KEY", "dev-key"))


def get_user_id() -> str:
    """Get the user ID for API calls."""
    return load_config().get("user_id", os.getenv("MEMORYCHAIN_USER_ID", "cli-user"))
