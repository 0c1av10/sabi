"""Test setup. Everything runs offline: SQLite per test, no Anthropic key, no WhatsApp."""
import os
import sys
from datetime import timedelta
from pathlib import Path

# Must be set BEFORE the app is imported (settings are read at import time).
os.environ.update({
    "ANTHROPIC_API_KEY": "",
    "AGENT_MOCK_MODE": "false",          # proves the demo engine is chosen because there is no key
    "WHATSAPP_MOCK_MODE": "true",
    "EVENTS_DEMO_SEED": "false",
    "EVENTS_ADMIN_EMAILS": "admin@example.com, second@example.com",
    "EVENTS_ADMIN_PASSWORD": "test-password-123",
    "SESSION_SECRET": "test-secret",
    "EVENTS_ALLOWED_PURCHASE_HOSTS": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

OFFICIAL_URL = "https://tickets.example.test/evento/1234"


@pytest_asyncio.fixture
async def Session(tmp_path, monkeypatch):
    """A fresh database for every test, wired into the app's `get_db`."""
    import app.db as dbmod
    import app.main as mainmod

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(dbmod, "engine", engine)
    monkeypatch.setattr(dbmod, "SessionLocal", maker)
    monkeypatch.setattr(mainmod, "_ready", True)  # skip first-request init/seed
    async with engine.begin() as conn:
        await conn.run_sync(dbmod.Base.metadata.create_all)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def client(Session):
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def make_event(Session):
    """Factory: creates a published upcoming event with zones directly in the DB."""
    from app.event_models import Event, EventZone
    from app.models import utcnow

    counter = {"n": 0}

    async def factory(*, city="Caracas", days=20, status="publicado", is_demo=False, url="",
                      active=True, name=None, zones=None, verified_days_ago=0):
        counter["n"] += 1
        n = counter["n"]
        verified = utcnow() - timedelta(days=verified_days_ago)
        zones = zones if zones is not None else [
            ("General", 2500, "USD", "disponible"),
            ("VIP", 6000, "USD", "disponible"),
            ("Palco", 9000, "USD", "agotado"),
        ]
        async with Session() as db:
            ev = Event(
                slug=f"evento-prueba-{n}", name=name or f"Evento Prueba {n}", artist=f"Artista {n}",
                city=city, venue="Recinto Prueba",
                starts_at=(utcnow() + timedelta(days=days)).replace(hour=12, minute=0, second=0, microsecond=0),
                description="Evento de prueba", status=status, active=active, is_demo=is_demo,
                purchase_url=url)
            ev.zones = [EventZone(name=z[0], price_minor=z[1], currency=z[2], availability=z[3],
                                  verified_at=verified) for z in zones]
            db.add(ev)
            await db.commit()
            await db.refresh(ev, ["zones"])
            return {"id": ev.id, "zones": {z.name: z.id for z in ev.zones}, "name": ev.name}

    return factory


@pytest_asyncio.fixture
async def tools(Session):
    """EventTools bound to a fresh server-side session."""
    from app.event_service import EventTools, get_or_create_session

    async with Session() as db:
        session = await get_or_create_session(db, None)
        await db.commit()
        yield EventTools(db, session)


@pytest_asyncio.fixture
async def admin_client(client):
    res = await client.post("/api/events/admin/login",
                            json={"email": "admin@example.com", "password": "test-password-123"})
    assert res.status_code == 200, res.text
    return client
