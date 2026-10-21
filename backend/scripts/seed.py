"""Seed: example restaurant with menu. Run: python -m scripts.seed"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Conversation, MenuItem, Restaurant  # noqa: E402
from sqlalchemy import select  # noqa: E402

MENU = [
    ("Pollo entero a la brasa", 21.00, "Platos", "Jugoso y dorado, la especialidad de la casa"),
    ("Medio pollo a la brasa", 11.00, "Platos", "Con arroz o yuca"),
    ("Pabellón criollo", 13.00, "Platos", "Carne mechada, arroz, caraotas y tajadas"),
    ("Cachapa con queso de mano", 9.00, "Platos", "Masa de maíz tierno"),
    ("Tequeños", 6.00, "Entradas", "5 unidades, con salsa de ajo"),
    ("Tostones playeros", 5.00, "Entradas", "Con queso rallado y salsa rosada"),
    ("Quesillo", 5.00, "Postres", "Casero"),
    ("Papelón con limón", 2.50, "Bebidas", "Natural, bien frío"),
    ("Jugo natural", 3.50, "Bebidas", "Parchita, fresa o melón"),
]


async def seed() -> bool:
    async with SessionLocal() as db:
        existing = (await db.execute(
            select(Restaurant).where(Restaurant.slug == "nacional"))).scalar_one_or_none()
        if existing:
            return False
        r = Restaurant(
            name="NACIONAL Restaurante",
            slug="nacional",
            pin="1234",
            owner_phone="59911111111",
            welcome_message="¡Hola! 👋 Soy Sabi de *NACIONAL Restaurante*. ¿Qué te provoca hoy?",
            opening_hours="Lun-Dom 7:00-23:00",
            currency="USD",
            exchange_rate=875.65,
            eur_rate=980.61,
            tagline="Pollo asado a la brasa, cachapas, parrillas, arepas y desayunos criollos en Lechería",
            email="hola@nacionalrestaurant.com",
            website="https://nacionalrestaurant.com/",
            delivery_zones='[{"name": "Lechería", "fee": 2.0}, {"name": "Barcelona", "fee": 3.0}, {"name": "Puerto La Cruz", "fee": 4.0}]',
            logo_url="https://nacionalrestaurant.com/favicon.svg",
            brand_color="#1A1714",
        )
        db.add(r)
        await db.flush()
        for name, price, cat, desc in MENU:
            db.add(MenuItem(restaurant_id=r.id, name=name, price=price,
                            category=cat, description=desc))
        await db.commit()
        return True


DEMO_CHATS = [
    ("59890000001", "Lucía R.", ["hola", "quiero 1 pollo entero a la brasa y 2 papelón con limón",
                                 "delivery", "dirección: Av. Principal de Lechería, edificio Mar Azul, apto 5", "sí"]),
    ("59890000002", "Martín P.", ["hola", "quiero 1 pabellón criollo y 1 jugo natural",
                                  "retiro", "sí"]),
    ("59890000003", "María G.", ["hola", "quiero 1 tequeños y 1 quesillo"]),
]


async def seed_demo_conversations() -> None:
    from app.service import handle_inbound_message

    async with SessionLocal() as db:
        r = (await db.execute(
            select(Restaurant).where(Restaurant.slug == "nacional"))).scalar_one()
        if (await db.execute(select(Conversation).limit(1))).first():
            return
        for phone, name, lines in DEMO_CHATS:
            for text in lines:
                await handle_inbound_message(db, r, phone, text, name)


async def main():
    await init_db()
    if not await seed():
        print("Seed ya aplicado (restaurante 'nacional' existe).")
    else:
        print("Seed listo: restaurante 'NACIONAL Restaurante' (slug: nacional, PIN: 1234) "
              f"con {len(MENU)} ítems de menú.")


if __name__ == "__main__":
    asyncio.run(main())
