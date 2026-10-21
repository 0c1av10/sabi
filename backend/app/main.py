from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import panel, store, webhook


_ready = False

# Delivery zones of NACIONAL's own storefront (provided by the owner). Applied once, only while the
# restaurant has no zones, so anything edited later in the panel is never overwritten.
KNOWN_DELIVERY_ZONES = {
    "nacional": [{"name": "Lechería", "fee": 2.0}, {"name": "Barcelona", "fee": 3.0},
                 {"name": "Puerto La Cruz", "fee": 4.0}],
}


async def backfill_known_delivery_zones() -> None:
    from sqlalchemy import select
    from . import delivery
    from .db import SessionLocal
    from .models import Restaurant
    async with SessionLocal() as session:
        changed = False
        for slug, zones in KNOWN_DELIVERY_ZONES.items():
            r = (await session.execute(select(Restaurant).where(Restaurant.slug == slug))).scalar_one_or_none()
            if r and not delivery.zones_of(r):
                r.delivery_zones = delivery.dump_zones(zones)
                changed = True
        if changed:
            await session.commit()


async def ensure_ready() -> None:
    global _ready
    if _ready:
        return
    await init_db()
    if settings.demo_autoseed:
        from scripts.seed import seed, seed_demo_conversations
        await seed()
        await seed_demo_conversations()
    await backfill_known_delivery_zones()
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
app.include_router(store.router)


@app.get("/health")
async def health():
    return {"ok": True}
