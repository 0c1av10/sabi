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


async def seed() -> bool:
    async with SessionLocal() as db:
        existing = (await db.execute(
            select(Restaurant).where(Restaurant.slug == "la-esquina"))).scalar_one_or_none()
        if existing:
            return False
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
        return True


DEMO_CHATS = [
    ("59890000001", "Lucía R.", ["hola", "quiero 2 milanesa napolitana y una gaseosa 1.5l",
                                 "delivery", "dirección: Av. Italia 1234, apto 5", "sí"]),
    ("59890000002", "Martín P.", ["hola", "quiero 1 hamburguesa completa y 2 agua mineral 500ml",
                                  "retiro", "sí"]),
    ("59890000003", "María G.", ["hola", "quiero 1 provoleta y 1 flan con dulce de leche"]),
]


async def seed_demo_conversations() -> None:
    from app.service import handle_inbound_message

    async with SessionLocal() as db:
        r = (await db.execute(
            select(Restaurant).where(Restaurant.slug == "la-esquina"))).scalar_one()
        for phone, name, lines in DEMO_CHATS:
            for text in lines:
                await handle_inbound_message(db, r, phone, text, name)


async def main():
    await init_db()
    if not await seed():
        print("Seed ya aplicado (restaurante 'la-esquina' existe).")
    else:
        print("Seed listo: restaurante 'La Esquina' (slug: la-esquina, PIN: 1234) "
              f"con {len(MENU)} ítems de menú.")


if __name__ == "__main__":
    asyncio.run(main())
