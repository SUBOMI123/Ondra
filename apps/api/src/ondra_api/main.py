from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from ondra_api import live
from ondra_api.config import get_settings
from ondra_api.db import no_tenant_session
from ondra_api.routers import appointments, auth, calls, conversations, data, follow_ups, integrations, knowledge, routing, settings, tasks, team, webhooks

app = FastAPI(title="Ondra API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().app_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(auth.me_router)
app.include_router(data.router)
app.include_router(webhooks.router)
app.include_router(settings.router)
app.include_router(team.router)
app.include_router(conversations.router)
app.include_router(tasks.router)
app.include_router(live.router)
app.include_router(appointments.router)
app.include_router(calls.router)
app.include_router(routing.router)
app.include_router(follow_ups.router)
app.include_router(integrations.router)
app.include_router(knowledge.router)
app.include_router(knowledge.ratings_router)


@app.get("/health", tags=["ops"])
async def health() -> dict:
    async with no_tenant_session() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ok"}
