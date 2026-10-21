from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import events, events_admin, panel, store, webhook


_ready = False

# Delivery zones of NACIONAL's own storefront (provided by the owner). Applied once, only while the
# restaurant has no zones, so anything edited later in the panel is never overwritten.
KNOWN_DELIVERY_ZONES = {
    "nacional": [{"name": "Lechería", "fee": 2.0}, {"name": "Barcelona", "fee": 3.0},
                 {"name": "Puerto La Cruz", "fee": 4.0}],
}


# Businesses onboarded from their public storefront (menu and prices as published there).
# Created once if missing; never touched afterwards so edits in the panel are kept.
KNOWN_BUSINESSES = [{
    "name": "MC Racuchos", "slug": "mc-racuchos",
    "tagline": "Pastelitos, arepas y tequeños en Lechería",
    "website": "https://mcracuchos.winktienda.com/",
    "opening_hours": "Abre desde las 4:30 p. m. Puedes programar tu pedido",
    "delivery_info": "El costo del delivery lo confirma el local.",
    "menu": [
        ("Pastelito de Pizza", 1.45, "Pastelitos", "Crujiente, relleno sabor pizza"),
        ("Pastelito de Queso", 1.45, "Pastelitos", ""),
        ("Pastelito de Pollo", 1.45, "Pastelitos", ""),
        ("Pastelito de Molida", 1.45, "Pastelitos", "Carne molida"),
        ("Pastelito de Carne Mechada", 1.45, "Pastelitos", ""),
        ("Pastelito de Mechada con queso", 1.45, "Pastelitos", ""),
        ("INDIVIDUAL 3 piezas", 4.90, "Combos", "3 pastelitos"),
        ("INDIVIDUAL 5 piezas", 7.30, "Combos", "5 pastelitos"),
        ("AREPAS 2 Pzas", 9.37, "Arepas", "2 arepas"),
        ("TEQUEÑERO 20 piezas", 26.00, "Para compartir", "20 tequeños"),
        ("PAPAQUESO 15 piezas", 16.00, "Para compartir", "15 piezas de papa y queso"),
        ("TRISABOR 15 piezas", 20.00, "Para compartir", "15 piezas, tres sabores"),
    ],
}]


async def seed_known_businesses() -> None:
    import secrets
    from sqlalchemy import select
    from .db import SessionLocal
    from .models import MenuItem, Restaurant
    async with SessionLocal() as session:
        for b in KNOWN_BUSINESSES:
            if (await session.execute(select(Restaurant.id).where(Restaurant.slug == b["slug"]))).first():
                continue
            r = Restaurant(
                name=b["name"], slug=b["slug"], pin=f"{secrets.randbelow(10000):04d}", owner_phone="",
                tagline=b["tagline"], website=b["website"], opening_hours=b["opening_hours"],
                delivery_info=b["delivery_info"],
                welcome_message=f"¡Hola! 👋 Soy Sabi, te ayudo con tu pedido en *{b['name']}*. ¿Qué te provoca hoy?")
            session.add(r)
            await session.flush()
            for n, price, cat, desc in b["menu"]:
                session.add(MenuItem(restaurant_id=r.id, name=n, price=price, category=cat, description=desc))
        await session.commit()


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


async def sync_events_if_empty() -> None:
    """First load: fill the catalog from the official platform when it has no real events yet."""
    if not settings.events_source_url:
        return
    from sqlalchemy import func, select
    from .db import SessionLocal
    from .event_models import Event
    from . import event_sync
    try:
        async with SessionLocal() as session:
            real = (await session.execute(select(func.count()).select_from(Event)
                                          .where(Event.is_demo.is_(False)))).scalar_one()
            if not real:
                await event_sync.sync(session)
    except Exception:
        pass  # source unreachable: keep whatever the catalog has


async def ensure_ready() -> None:
    global _ready
    if _ready:
        return
    await init_db()
    if settings.demo_autoseed:
        from scripts.seed import seed, seed_demo_conversations
        await seed()
        await seed_demo_conversations()
    if settings.events_demo_seed:
        from .db import SessionLocal
        from .event_seed import seed_demo_events
        async with SessionLocal() as session:
            await seed_demo_events(session)  # no-op unless the events catalog is empty
    await sync_events_if_empty()
    await seed_known_businesses()
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
app.include_router(events.router)
app.include_router(events_admin.router)


@app.get("/health")
async def health():
    return {"ok": True}
