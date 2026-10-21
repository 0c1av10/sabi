"""Fictional demo catalog. Clearly marked is_demo; purchase links stay empty on purpose."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .event_models import Event, EventZone
from .models import utcnow


def _starts(days: int, local_hour: int) -> datetime:
    # `local_hour` o'clock in America/Caracas (UTC-4 all year), stored as naive UTC.
    day = (utcnow() + timedelta(days=days)).date()
    return datetime(day.year, day.month, day.day, local_hour) + timedelta(hours=4)


async def seed_demo_events(db: AsyncSession, force: bool = False) -> bool:
    """Create three fictional events if the catalog is empty (or always with force=True)."""
    if not force and (await db.execute(select(func.count(Event.id)))).scalar_one():
        return False
    now = utcnow()
    stale = now - timedelta(days=10)
    specs = [
        dict(slug="demo-noches-de-araguaney", name="Noches de Araguaney", artist="Banda Ficticia Aurora",
             city="Caracas", venue="Teatro Demo del Este", starts_at=_starts(21, 20),
             description="Evento ficticio de demostración. Una noche de música en vivo para probar el flujo de Sabi.",
             zones=[("General", 2500, "USD", "disponible", now), ("VIP", 6000, "USD", "disponible", now),
                    ("Palco", 9000, "USD", "agotado", now)]),
        dict(slug="demo-sol-de-medianoche", name="Sol de Medianoche", artist="DJ Imaginario",
             city="Valencia", venue="Arena Demo", starts_at=_starts(35, 21),
             description="Evento ficticio de demostración. Noche electrónica para probar zonas y cantidades.",
             zones=[("Pista", 1800, "USD", "disponible", now), ("Tribuna", 3000, "USD", "por_confirmar", now)]),
        dict(slug="demo-tarde-de-joropo-y-rock", name="Tarde de Joropo y Rock", artist="Orquesta Inventada",
             city="Maracaibo", venue="Anfiteatro Demo", starts_at=_starts(50, 17),
             description="Evento ficticio de demostración con datos sin verificar recientemente, para ver los avisos.",
             zones=[("General", 1500, "USD", "disponible", stale),
                    ("Preferencial", 4000, "USD", "disponible", stale)]),
    ]
    for spec in specs:
        zones = spec.pop("zones")
        event = Event(status="publicado", active=True, is_demo=True, purchase_url="",
                      timezone="America/Caracas", **spec)
        event.zones = [EventZone(name=n, price_minor=p, currency=c, availability=a, verified_at=v)
                       for n, p, c, a, v in zones]
        db.add(event)
    await db.commit()
    return True
