from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import panel, webhook


_ready = False


async def ensure_ready() -> None:
    global _ready
    if _ready:
        return
    await init_db()
    if settings.demo_autoseed:
        from scripts.seed import seed, seed_demo_conversations
        await seed()
        await seed_demo_conversations()
    _ready = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_ready()
    yield


app = FastAPI(title="Sabi", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def init_on_first_request(request: Request, call_next):
    await ensure_ready()
    return await call_next(request)


app.include_router(webhook.router)
app.include_router(panel.router)


@app.get("/health")
async def health():
    return {"ok": True}
