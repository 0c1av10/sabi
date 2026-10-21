"""Core flow: inbound WhatsApp message -> agent -> (maybe) pending order -> owner notification.
And: owner approves/edits/rejects -> customer confirmation via WhatsApp."""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .bcv import refresh_rates
from .config import settings
from .agent import delivery_fee_for, fmt_money, rates_of, run_agent, summarize_order
from .models import (Conversation, Customer, MenuItem, Message, Order,
                     OrderItem, OrderStatus, PaymentStatus, Restaurant, utcnow)
from .whatsapp import send_whatsapp_message


async def get_or_create_conversation(db: AsyncSession, restaurant: Restaurant,
                                     phone: str, name: str = "") -> Conversation:
    customer = (await db.execute(select(Customer).where(
        Customer.restaurant_id == restaurant.id, Customer.phone == phone))).scalar_one_or_none()
    if not customer:
        customer = Customer(restaurant_id=restaurant.id, phone=phone, name=name)
        db.add(customer)
        await db.flush()
    elif name and not customer.name:
        customer.name = name

    conv = (await db.execute(select(Conversation).where(
        Conversation.restaurant_id == restaurant.id,
        Conversation.customer_id == customer.id,
        Conversation.status == "open").options(selectinload(Conversation.messages))
    )).scalars().first()
    if not conv:
        conv = Conversation(restaurant_id=restaurant.id, customer_id=customer.id)
        db.add(conv)
        await db.flush()
    return conv


RATE_LIMIT_REPLY = ("Recibimos muchos mensajes tuyos en poco tiempo. "
                    "Espera un rato y vuelve a escribirnos, por favor 🙏")


async def recent_inbound_count(db: AsyncSession, customer_id: int | None = None) -> int:
    q = select(func.count(Message.id)).join(
        Conversation, Message.conversation_id == Conversation.id).where(
        Message.direction == "inbound", Message.created_at >= utcnow() - timedelta(hours=1))
    if customer_id is not None:
        q = q.where(Conversation.customer_id == customer_id)
    return (await db.execute(q)).scalar_one()


async def handle_inbound_message(db: AsyncSession, restaurant: Restaurant,
                                 phone: str, body: str, name: str = "",
                                 external_id: str | None = None) -> str:
    """Process one inbound customer message. Returns the reply text sent."""
    body = body[:settings.max_message_chars]
    if external_id and (await db.execute(select(Message.id).where(
            Message.external_id == external_id))).first():
        return ""
    conv = await get_or_create_conversation(db, restaurant, phone, name)
    sent = await recent_inbound_count(db, conv.customer_id)
    db.add(Message(conversation_id=conv.id, direction="inbound", body=body,
                   external_id=external_id))
    await db.commit()  # visible to concurrent webhook retries (dedupe)
    if sent >= settings.rate_limit_per_phone_hour:
        if sent == settings.rate_limit_per_phone_hour:
            db.add(Message(conversation_id=conv.id, direction="outbound", body=RATE_LIMIT_REPLY))
            await send_whatsapp_message(phone, RATE_LIMIT_REPLY)
        await db.commit()
        return RATE_LIMIT_REPLY
    await refresh_rates(restaurant)

    if conv.status == "handed_to_owner":
        return ""  # human is handling it; just log

    msgs = (await db.execute(select(Message).where(
        Message.conversation_id == conv.id).order_by(Message.created_at))).scalars().all()
    history = [(m.direction, m.body) for m in msgs]
    result = await run_agent(db, restaurant, conv, history, body)
    conv.state_json = json.dumps(result.state, ensure_ascii=False)

    if result.action == "handoff":
        conv.status = "handed_to_owner"

    if result.reply:
        db.add(Message(conversation_id=conv.id, direction="outbound", body=result.reply))
        await send_whatsapp_message(phone, result.reply)

    if result.action == "submit_order" and result.order:
        order = await create_pending_order(db, restaurant, conv, result.order)
        await notify_owner_new_order(db, restaurant, order)

    await db.commit()
    return result.reply


async def create_pending_order(db: AsyncSession, restaurant: Restaurant,
                               conv: Conversation, draft: dict) -> Order:
    items_by_name = {i.name.lower(): i for i in (await db.execute(select(MenuItem).where(
        MenuItem.restaurant_id == restaurant.id))).scalars().all()}
    fee = delivery_fee_for(draft, restaurant.delivery_fee)
    _, total = summarize_order(draft, items_by_name, rates_of(restaurant), fee)

    order = Order(
        restaurant_id=restaurant.id,
        conversation_id=conv.id,
        customer_id=conv.customer_id,
        order_type=draft.get("order_type") or "retiro",
        address=draft.get("address") or "",
        notes=draft.get("notes") or "",
        total=total,
        delivery_fee=fee,
        payment_method=draft.get("payment_method") or "",
        payment_reference=draft.get("payment_reference") or "",
        payment_status=PaymentStatus.submitted if draft.get("payment_method") else PaymentStatus.pending,
    )
    db.add(order)
    await db.flush()
    new_items = []
    for oi in draft.get("items", []):
        mi = items_by_name.get(str(oi.get("name", "")).strip().lower())
        if not mi:
            continue
        new_items.append(OrderItem(
            order_id=order.id,
            menu_item_id=mi.id,
            name=mi.name,
            quantity=int(oi.get("quantity", 1)),
            unit_price=mi.price,
            extras=oi.get("extras", ""),
            notes=oi.get("notes", ""),
        ))
        db.add(new_items[-1])
    order.total = sum(i.unit_price * i.quantity for i in new_items) + fee
    conv.status = "closed"
    await db.flush()
    return order


async def notify_owner_new_order(db: AsyncSession, restaurant: Restaurant, order: Order) -> None:
    if not restaurant.owner_phone:
        return
    await db.refresh(order, ["items"])
    items = ", ".join(f"{i.quantity}x {i.name}" for i in order.items)
    await send_whatsapp_message(
        restaurant.owner_phone,
        f"🔔 Nuevo pedido #{order.id} pendiente de pago y aprobación: {items} — "
        f"total {fmt_money(order.total, *rates_of(restaurant))}. Confirma el pago y apruébalo en el panel de Sabi.",
    )


async def get_customer_phone(db: AsyncSession, order: Order) -> str:
    customer = await db.get(Customer, order.customer_id)
    return customer.phone if customer else ""


async def approve_order(db: AsyncSession, restaurant: Restaurant, order: Order,
                        edited: bool = False) -> None:
    if order.payment_status != PaymentStatus.confirmed:
        raise ValueError("Primero confirma el pago del cliente.")
    order.status = OrderStatus.edited if edited else OrderStatus.approved
    order.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.refresh(order, ["items"])
    items = ", ".join(f"{i.quantity}x {i.name}" for i in order.items)
    extra = f" (con ajustes: {order.edit_summary})" if edited and order.edit_summary else ""
    phone = await get_customer_phone(db, order)
    msg = (f"✅ ¡Pedido confirmado por {restaurant.name}!{extra}\n"
           f"{items}\nTotal: {fmt_money(order.total, *rates_of(restaurant))}\n¡Gracias!")
    db.add(Message(conversation_id=order.conversation_id, direction="outbound", body=msg))
    if phone:
        await send_whatsapp_message(phone, msg)
    await db.commit()


async def reject_order(db: AsyncSession, restaurant: Restaurant, order: Order, reason: str) -> None:
    order.status = OrderStatus.rejected
    order.rejection_reason = reason
    order.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    phone = await get_customer_phone(db, order)
    msg = (f"Lo sentimos, tu pedido no pudo confirmarse en {restaurant.name}."
           + (f" Motivo: {reason}" if reason else ""))
    db.add(Message(conversation_id=order.conversation_id, direction="outbound", body=msg))
    if phone:
        await send_whatsapp_message(phone, msg)
    await db.commit()
