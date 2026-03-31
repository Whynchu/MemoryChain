from pydantic import BaseModel
import os


class Settings(BaseModel):
    api_key: str = os.getenv("MEMORYCHAIN_API_KEY", "dev-key")
    db_path: str = os.getenv("MEMORYCHAIN_DB_PATH", "memorychain.db")
    llm_provider: str = os.getenv("MEMORYCHAIN_LLM_PROVIDER", "local")
    llm_model: str = os.getenv("MEMORYCHAIN_LLM_MODEL", "gpt-4o-mini")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")


settings = Settings()
