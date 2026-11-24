"""Customer requests for businesses Sabi does not have yet.

When someone asks for a business outside the verified catalog, the request is
recorded here so the team can see demand and onboard those businesses. Only the
business name as written, plus the city when the customer stated it: never the
customer's phone or any other personal data. Decided 2026-11-23
(docs/REQUESTED_BUSINESSES.md).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .concierge import _plain
from .models import RequestedBusiness, utcnow


def name_key(name: str) -> str:
    """Normalized dedupe key: accents and case removed, whitespace collapsed."""
    return " ".join(_plain(name).split())[:150]


async def record(db: AsyncSession, name: str, city: str = "") -> None:
    """Count one request for `name`; repeat asks raise the counter instead of duplicating."""
    key = name_key(name)
    if not key:
        return
    row = (await db.execute(
        select(RequestedBusiness).where(RequestedBusiness.name_key == key)
    )).scalar_one_or_none()
    if row:
        row.requests += 1
        row.last_requested_at = utcnow()
        if city.strip() and not row.city:
            row.city = city.strip()[:100]
    else:
        db.add(RequestedBusiness(name=name.strip()[:200], name_key=key,
                                 city=city.strip()[:100]))
    await db.commit()
