from fastapi import FastAPI

from .config import settings
from .routers import activities, audit_log, chat, checkins, engagement, goals, health, heuristics, ingest, insights, journal, metrics, prompt_cycles, prompts, protocols, questionnaires, reviews, search, tasks, users
from .services.seed_templates import seed_default_templates
from .storage.db import connect, initialize
from .storage.repository import Repository


def create_app() -> FastAPI:
    app = FastAPI(title="MemoryChain API", version="0.2.0")

    conn = connect(settings.db_path)
    initialize(conn)
    app.state.repo = Repository(conn)
    seed_default_templates(app.state.repo)

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
    app.include_router(prompt_cycles.router)
    app.include_router(engagement.router)
    app.include_router(audit_log.router)
    app.include_router(activities.router)
    app.include_router(metrics.router)
    app.include_router(protocols.router)  
    app.include_router(questionnaires.router)
    app.include_router(insights.router)
    app.include_router(heuristics.router)
    app.include_router(users.router)
    return app


app = create_app()
