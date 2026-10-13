from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..bcv import fetch_bcv, refresh_rates
from ..auth import COOKIE_NAME, current_restaurant, make_token
from ..db import get_db
from ..models import (Conversation, Customer, MenuItem, Message, Order,
                      OrderItem, Restaurant)
from ..schemas import (ConversationOut, LoginIn, MenuItemIn, MenuItemOut,
                       OrderEditIn, OrderItemOut, OrderOut, RejectIn,
                       RestaurantOut, RestaurantSettingsIn)
from ..service import approve_order, reject_order

router = APIRouter(prefix="/api", tags=["panel"])


@router.post("/auth/login")
async def login(data: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    restaurant = (await db.execute(
        select(Restaurant).where(Restaurant.slug == data.slug))).scalar_one_or_none()
    if not restaurant or restaurant.pin != data.pin:
        raise HTTPException(401, "Slug o PIN incorrecto")
    token = make_token(restaurant.id)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return {"token": token, "restaurant": RestaurantOut.model_validate(restaurant)}


@router.get("/me", response_model=RestaurantOut)
async def me(restaurant: Restaurant = Depends(current_restaurant),
             db: AsyncSession = Depends(get_db)):
    if await refresh_rates(restaurant):
        await db.commit()
    return restaurant


@router.get("/bcv")
async def bcv_rates():
    data = await fetch_bcv()
    if not data:
        raise HTTPException(502, "No se pudo consultar la tasa BCV")
    return data


@router.post("/settings/bcv", response_model=RestaurantOut)
async def sync_bcv(restaurant: Restaurant = Depends(current_restaurant),
                   db: AsyncSession = Depends(get_db)):
    if not await refresh_rates(restaurant, force=True):
        raise HTTPException(502, "No se pudo consultar la tasa BCV")
    await db.commit()
    return restaurant


@router.put("/settings", response_model=RestaurantOut)
async def update_settings(data: RestaurantSettingsIn,
                          restaurant: Restaurant = Depends(current_restaurant),
                          db: AsyncSession = Depends(get_db)):
    for f in ("welcome_message", "opening_hours", "owner_phone", "name", "bcv_auto",
              "email", "website", "tagline", "logo_url", "brand_color"):
        v = getattr(data, f)
        if v is not None:
            setattr(restaurant, f, v)
    if restaurant.bcv_auto:
        await refresh_rates(restaurant, force=True)
    else:
        for f in ("exchange_rate", "eur_rate"):
            v = getattr(data, f)
            if v is not None:
                setattr(restaurant, f, v)
    await db.commit()
    return restaurant


# ---- Menu CRUD ----

@router.get("/menu", response_model=list[MenuItemOut])
async def list_menu(restaurant: Restaurant = Depends(current_restaurant),
                    db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(MenuItem).where(
        MenuItem.restaurant_id == restaurant.id))).scalars().all()


@router.post("/menu", response_model=MenuItemOut)
async def create_menu_item(data: MenuItemIn,
                           restaurant: Restaurant = Depends(current_restaurant),
                           db: AsyncSession = Depends(get_db)):
    item = MenuItem(restaurant_id=restaurant.id, **data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/menu/{item_id}", response_model=MenuItemOut)
async def update_menu_item(item_id: int, data: MenuItemIn,
                           restaurant: Restaurant = Depends(current_restaurant),
                           db: AsyncSession = Depends(get_db)):
    item = await db.get(MenuItem, item_id)
    if not item or item.restaurant_id != restaurant.id:
        raise HTTPException(404)
    for k, v in data.model_dump().items():
        setattr(item, k, v)
    await db.commit()
    return item


@router.delete("/menu/{item_id}")
async def delete_menu_item(item_id: int,
                           restaurant: Restaurant = Depends(current_restaurant),
                           db: AsyncSession = Depends(get_db)):
    item = await db.get(MenuItem, item_id)
    if not item or item.restaurant_id != restaurant.id:
        raise HTTPException(404)
    await db.delete(item)
    await db.commit()
    return {"ok": True}


# ---- Orders / approval inbox ----

def order_out(order: Order, customer: Customer | None) -> OrderOut:
    return OrderOut(
        id=order.id, status=order.status.value, order_type=order.order_type,
        address=order.address, notes=order.notes, total=order.total,
        rejection_reason=order.rejection_reason, edit_summary=order.edit_summary,
        created_at=order.created_at, decided_at=order.decided_at,
        customer_phone=customer.phone if customer else "",
        customer_name=customer.name if customer else "",
        source=order.source or "whatsapp",
        items=[OrderItemOut.model_validate(i) for i in order.items],
    )


async def _orders(db: AsyncSession, restaurant_id: int, status: str | None = None):
    q = select(Order).where(Order.restaurant_id == restaurant_id).options(
        selectinload(Order.items)).order_by(Order.created_at.desc())
    if status:
        q = q.where(Order.status == status)
    orders = (await db.execute(q)).scalars().all()
    out = []
    for o in orders:
        out.append(order_out(o, await db.get(Customer, o.customer_id)))
    return out


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(status: str | None = None,
                      restaurant: Restaurant = Depends(current_restaurant),
                      db: AsyncSession = Depends(get_db)):
    return await _orders(db, restaurant.id, status)


async def _get_order(db: AsyncSession, restaurant: Restaurant, order_id: int) -> Order:
    order = (await db.execute(select(Order).where(Order.id == order_id).options(
        selectinload(Order.items)))).scalar_one_or_none()
    if not order or order.restaurant_id != restaurant.id:
        raise HTTPException(404)
    return order


@router.post("/orders/{order_id}/approve", response_model=OrderOut)
async def approve(order_id: int, restaurant: Restaurant = Depends(current_restaurant),
                  db: AsyncSession = Depends(get_db)):
    order = await _get_order(db, restaurant, order_id)
    await approve_order(db, restaurant, order)
    return order_out(order, await db.get(Customer, order.customer_id))


@router.post("/orders/{order_id}/edit", response_model=OrderOut)
async def edit(order_id: int, data: OrderEditIn,
               restaurant: Restaurant = Depends(current_restaurant),
               db: AsyncSession = Depends(get_db)):
    order = await _get_order(db, restaurant, order_id)
    for f in ("order_type", "address", "notes", "edit_summary"):
        v = getattr(data, f)
        if v is not None:
            setattr(order, f, v)
    if data.items is not None:
        for i in list(order.items):
            await db.delete(i)
        await db.flush()
        for oi in data.items:
            db.add(OrderItem(order_id=order.id, **oi.model_dump()))
        await db.flush()
        await db.refresh(order, ["items"])
        order.total = sum(i.unit_price * i.quantity for i in order.items)
    await approve_order(db, restaurant, order, edited=True)
    return order_out(order, await db.get(Customer, order.customer_id))


@router.post("/orders/{order_id}/reject", response_model=OrderOut)
async def reject(order_id: int, data: RejectIn,
                 restaurant: Restaurant = Depends(current_restaurant),
                 db: AsyncSession = Depends(get_db)):
    order = await _get_order(db, restaurant, order_id)
    await reject_order(db, restaurant, order, data.reason)
    return order_out(order, await db.get(Customer, order.customer_id))


# ---- Log / day view ----

@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(restaurant: Restaurant = Depends(current_restaurant),
                             db: AsyncSession = Depends(get_db)):
    convs = (await db.execute(select(Conversation).where(
        Conversation.restaurant_id == restaurant.id).options(
        selectinload(Conversation.messages)).order_by(Conversation.updated_at.desc())
    )).scalars().all()
    out = []
    for c in convs:
        customer = await db.get(Customer, c.customer_id)
        out.append(ConversationOut(
            id=c.id, status=c.status, created_at=c.created_at, updated_at=c.updated_at,
            customer_phone=customer.phone if customer else "",
            customer_name=customer.name if customer else "",
            messages=list(c.messages)))
    return out


@router.get("/today")
async def today(restaurant: Restaurant = Depends(current_restaurant),
                db: AsyncSession = Depends(get_db)):
    start = datetime.now(timezone.utc).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    orders = (await db.execute(select(Order).where(
        Order.restaurant_id == restaurant.id, Order.created_at >= start))).scalars().all()
    convs = (await db.execute(select(Conversation).where(
        Conversation.restaurant_id == restaurant.id,
        Conversation.updated_at >= start))).scalars().all()
    return {
        "orders_total": len(orders),
        "approved": sum(1 for o in orders if o.status.value in ("approved", "edited")),
        "rejected": sum(1 for o in orders if o.status.value == "rejected"),
        "pending": sum(1 for o in orders if o.status.value == "pending"),
        "open_conversations": sum(1 for c in convs if c.status == "open"),
    }
