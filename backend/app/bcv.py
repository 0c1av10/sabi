"""Tasas oficiales del BCV (Bs por USD y por EUR) vía ve.dolarapi.com."""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

API = "https://ve.dolarapi.com/v1"
TTL_SECONDS = 3600
REFRESH_EVERY = timedelta(hours=1)
_cache: dict = {}


async def fetch_bcv() -> Optional[dict]:
    if _cache and time.time() - _cache["at"] < TTL_SECONDS:
        return _cache["data"]
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            usd = (await c.get(f"{API}/dolares/oficial")).json()
            eur = (await c.get(f"{API}/euros/oficial")).json()
        data = {
            "usd": round(float(usd["promedio"]), 2),
            "eur": round(float(eur["promedio"]), 2),
            "fecha": str(usd.get("fechaActualizacion", ""))[:10],
            "fuente": "BCV",
        }
    except Exception:
        return _cache.get("data")
    _cache.update(at=time.time(), data=data)
    return data


async def refresh_rates(restaurant, force: bool = False) -> bool:
    """Updates the restaurant's rates from BCV when auto mode is on. Keeps the old rates if BCV is unreachable."""
    if not (force or restaurant.bcv_auto):
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    last = restaurant.rates_updated_at
    if not force and last and now - last.replace(tzinfo=None) < REFRESH_EVERY:
        return False
    data = await fetch_bcv()
    if not data:
        return False
    restaurant.exchange_rate = data["usd"]
    restaurant.eur_rate = data["eur"]
    restaurant.rates_date = data["fecha"]
    restaurant.rates_updated_at = now
    return True
