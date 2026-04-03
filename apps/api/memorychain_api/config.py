from pydantic import BaseModel
import json
import os
from pathlib import Path


def _read_memorychain_config() -> dict:
    """Read ~/.memorychain/config.json if it exists."""
    config_file = Path.home() / ".memorychain" / "config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


_mc_config = _read_memorychain_config()


class Settings(BaseModel):
    api_key: str = os.getenv("MEMORYCHAIN_API_KEY", "dev-key")
    db_path: str = os.getenv("MEMORYCHAIN_DB_PATH", "memorychain.db")
    llm_provider: str = os.getenv(
        "MEMORYCHAIN_LLM_PROVIDER",
        _mc_config.get("llm_provider", "local"),
    )
    llm_model: str = os.getenv("MEMORYCHAIN_LLM_MODEL", "gpt-4o-mini")
    openai_api_key: str | None = os.getenv(
        "OPENAI_API_KEY",
        _mc_config.get("openai_api_key"),
    )


settings = Settings()
