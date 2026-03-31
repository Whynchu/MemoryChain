from __future__ import annotations

from fastapi import Depends, Request

from .auth import require_api_key
from .storage.repository import Repository


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


def protected_repo(_: None = Depends(require_api_key), repo: Repository = Depends(get_repo)) -> Repository:
    return repo
