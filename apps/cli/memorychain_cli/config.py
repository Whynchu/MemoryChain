"""CLI configuration — reads from environment variables."""

import os


API_BASE_URL = os.getenv("MEMORYCHAIN_API_URL", "http://localhost:8000")
API_KEY = os.getenv("MEMORYCHAIN_API_KEY", "dev-key")
USER_ID = os.getenv("MEMORYCHAIN_USER_ID", "cli-user")
