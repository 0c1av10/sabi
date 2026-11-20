"""Replay of the WhatsApp sequence reported on 2026-11-20 (screenshots from the user).
Runs the real webhook pipeline offline (mock agent engine, mock WhatsApp) and prints
Sabi's routing decision and reply for each message, including the 30-minute gap that
used to drop the open order. Run: python -m scripts.replay_20261120"""
import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

os.environ.update({
    "ANTHROPIC_API_KEY": "",
    "WHATSAPP_MOCK_MODE": "true",
    "EVENTS_DEMO_SEED": "false",
    "SESSION_SECRET": "replay-secret",
    "EVENTS_ADMIN_EMAILS": "",
    "EVENTS_ADMIN_PASSWORD": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

import app.db as dbmod  # noqa: E402
from app import conversation_focus as focus  # noqa: E402
from app.main import KNOWN_BUSINESSES  # noqa: E402
from app.models import MenuItem, Restaurant, utcnow  # noqa: E402
from app.routers import webhook  # noqa: E402
from app.service import handle_inbound_message  # noqa: E402
from app.whatsapp import sent_log  # noqa: E402

SEQUENCE = [
    ("Hola tengo hambre quiero un plan cool de hoy", 0),
    ("Dame todos los restaurantes que tengas", 1),
    ("Y nacional ?", 1),
    ("Nacional", 1),
    ("Restaurante", 1),
    ("Lecheria", 1),
    # 33 minutes of silence: the focus window closes before the next message.
    ("Si dame ese pero pídelo mañana a las 9 am", 33),
    ("Sera delivery", 1),
    ("Agrégale un refresco", 1),
    ("Dame todos los restaurantes que tengas", 1),
]


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    dbmod.engine = engine
    dbmod.SessionLocal = maker
    async with engine.begin() as conn:
        await conn.run_sync(dbmod.Base.metadata.create_all)
    async with maker() as db:
        for b in KNOWN_BUSINESSES:
            r = Restaurant(name=b["name"], slug=b["slug"], pin="0000", tagline=b["tagline"])
            db.add(r)
            await db.flush()
            for n, price, cat, desc in b["menu"]:
                db.add(MenuItem(restaurant_id=r.id, name=n, price=price, category=cat, description=desc))
        n = Restaurant(name="NACIONAL Restaurante", slug="nacional", pin="0000",
                       tagline="Pollo asado y cachapas en Lechería")
        db.add(n)
        await db.flush()
        db.add(MenuItem(restaurant_id=n.id, name="Pabellón criollo", price=13.0, category="Platos"))
        db.add(MenuItem(restaurant_id=n.id, name="Refresco", price=2.0, category="Bebidas"))
        await db.commit()

    phone = "584120000000"
    for text, gap_minutes in SEQUENCE:
        if gap_minutes > 5:
            async with maker() as db:
                row = await focus.get(db, phone)
                if row:
                    row.expires_at = utcnow() - timedelta(minutes=1)
                    await db.commit()
            print(f"   ... {gap_minutes} min de silencio (ventana de contexto vencida) ...")
        sent_log.clear()
        async with maker() as db:
            events_reply = await webhook._events_route(db, phone, text, None, "Cliente Test")
            if events_reply is not None:
                route = "concierge/eventos"
            else:
                restaurant, routed, concierge_reply = await webhook._resolve(db, phone, text)
                if restaurant:
                    route = f"local: {restaurant.name}"
                    await handle_inbound_message(db, restaurant, phone, routed, "Cliente Test")
                else:
                    route = "concierge"
                    if concierge_reply:
                        sent_log.append({"body": concierge_reply})
        replies = [e.get("body", e) for e in sent_log]
        print(f"\n> {text}\n  ruta: {route}")
        for r in replies:
            print("  sabi:", str(r).replace("\n", " / ")[:220])


if __name__ == "__main__":
    asyncio.run(main())
