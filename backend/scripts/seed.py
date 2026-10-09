"""Seed: example restaurant with menu. Run: python -m scripts.seed"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import MenuItem, Restaurant  # noqa: E402
from sqlalchemy import select  # noqa: E402

MENU = [
    ("Milanesa napolitana", 4500, "Platos", "Con salsa y mozzarella, guarnición incluida"),
    ("Hamburguesa completa", 3800, "Platos", "Medallón casero, queso, huevo, papas"),
    ("Ensalada César", 2900, "Platos", "Pollo grillado, crutones, parmesano"),
    ("Empanadas de carne (docena)", 3600, "Entradas", "Fritas u horno"),
    ("Provoleta", 2200, "Entradas", "Con orégano y tomate"),
    ("Flan con dulce de leche", 1500, "Postres", "Casero"),
    ("Gaseosa 1.5L", 1200, "Bebidas", "Coca-Cola o Sprite"),
    ("Agua mineral 500ml", 800, "Bebidas", "Con o sin gas"),
]


async def main():
    await init_db()
    async with SessionLocal() as db:
        existing = (await db.execute(
            select(Restaurant).where(Restaurant.slug == "la-esquina"))).scalar_one_or_none()
        if existing:
            print("Seed ya aplicado (restaurante 'la-esquina' existe).")
            return
        r = Restaurant(
            name="La Esquina",
            slug="la-esquina",
            pin="1234",
            owner_phone="59911111111",
            welcome_message="¡Hola! 👋 Soy Sabi de *La Esquina*. ¿Qué te provoca hoy?",
            opening_hours="Lun-Dom 12:00-15:00 y 19:00-23:30",
            currency="$",
        )
        db.add(r)
        await db.flush()
        for name, price, cat, desc in MENU:
            db.add(MenuItem(restaurant_id=r.id, name=name, price=price,
                            category=cat, description=desc))
        await db.commit()
        print("Seed listo: restaurante 'La Esquina' (slug: la-esquina, PIN: 1234) "
              f"con {len(MENU)} ítems de menú.")


if __name__ == "__main__":
    asyncio.run(main())
