"""CLI configuration — reads from ~/.memorychain/config.json, falls back to env vars."""

from . import settings


API_BASE_URL = settings.get_api_url()
API_KEY = settings.get_api_key()
USER_ID = settings.get_user_id()
