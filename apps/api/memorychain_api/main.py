from fastapi import FastAPI

from .config import settings
from .routers import chat, checkins, goals, health, ingest, journal, prompts, reviews, search, tasks
from .storage.db import connect, initialize
from .storage.repository import Repository


def create_app() -> FastAPI:
    app = FastAPI(title="MemoryChain API", version="0.2.0")

    conn = connect(settings.db_path)
    initialize(conn)
    app.state.repo = Repository(conn)

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(ingest.router)
    app.include_router(goals.router)
    app.include_router(tasks.router)
    app.include_router(journal.router)
    app.include_router(checkins.router)
    app.include_router(reviews.router)
    app.include_router(search.router)
    app.include_router(prompts.router)
    return app


app = create_app()
