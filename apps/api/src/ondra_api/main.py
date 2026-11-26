from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from ondra_api.config import get_settings
from ondra_api.db import no_tenant_session
from ondra_api.routers import auth, data, webhooks

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


@app.get("/health", tags=["ops"])
async def health() -> dict:
    async with no_tenant_session() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ok"}
