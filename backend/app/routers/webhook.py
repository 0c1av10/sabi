import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import restaurant_for_message, restaurant_by_mention, named_business_query
from ..config import settings
from ..db import get_db
from ..models import Conversation, Customer, Restaurant
from ..reactions import reaction_for
from ..inbound_receipts import claim_inbound
from ..whatsapp import incoming_reply_context, digits, send_whatsapp_message, send_whatsapp_reaction, send_whatsapp_typing, zernio_conversations
from ..service import handle_inbound_message, recent_inbound_count
from ..cinema_whatsapp import explicit_cinema, wants_cinema, handle_cinema_whatsapp
from ..event_whatsapp import handle_event_whatsapp, wants_events
from .. import concierge, gym_whatsapp, memory, pilot_yummy, shopping_inquiry, place_source, venezuela, conversation_focus as focus

router = APIRouter(tags=["whatsapp"])


WELCOME_MESSAGE = concierge.WELCOME
_WELCOME_COOLDOWN = timedelta(hours=1)
_welcomed: dict[str, datetime] = {}  # per warm instance: avoids repeating the welcome on every message



async def _pilot_route(db: AsyncSession, phone: str, body: str) -> bool:
    """Yummy Rides quote pilot: personal quote requests reach it BEFORE
    restaurant routing - the user's own WhatsApp asks Sabi directly, with no
    business involved. Quote-only; the reply itself says no ride is ordered."""
    reply = await pilot_yummy.create_quote_job(db, phone, body)
    if reply:
        await send_whatsapp_message(phone, reply)
        return True
    return False

async def _react(phone: str, message_id: str | None, body: str) -> None:
    """Best-effort emoji reaction chosen by message type; must never break the reply."""
    emoji = reaction_for(body)
    if emoji and message_id:
        try:
            await send_whatsapp_reaction(phone, message_id, emoji)
        except Exception:  # noqa: BLE001
            pass


async def _close_open_conversations(db: AsyncSession, phone: str) -> None:
    ids = (await db.execute(
        select(Conversation.id).join(Customer, Conversation.customer_id == Customer.id)
        .where(Customer.phone == phone, Conversation.status == "open"))).scalars().all()
    if ids:
        await db.execute(update(Conversation).where(Conversation.id.in_(ids)).values(status="closed"))
        await db.commit()


async def _unresolved_place_reply(db,phone,body):
    named=named_business_query(body)
    if not named:return None
    entity,city=named
    previous=await focus.get(db,phone)
    if not city and previous and previous.domain=='place' and (not previous.entity or concierge._plain(previous.entity)==concierge._plain(entity)):
        city=previous.city
    known=await restaurant_by_mention(db,entity)
    # A catalog business that registered delivery to the city is not an unresolved place.
    if known and (not city or await venezuela.covers(db,known,city)):
        return None
    await focus.save(db,phone,domain='place',entity=entity,city=city)
    return (f'Estás consultando por {entity}'+(f' en {city}.' if city else '.')+
            ' No lo tengo identificado en el catálogo verificado y no voy a usar el menú ni el delivery de otro local. Si tienes su enlace oficial, pásamelo para revisar esa fuente.')


_SWITCH='cambio de local: '
_YES=re.compile(r'^\s*(?:s[ií]|dale|ok|claro|listo|de una|perfecto)\b',re.I)
_NO=re.compile(r'^\s*(?:no\b|seguimos|sigo|mejor no|me quedo)',re.I)


async def _silent_business_switch(db,phone,body,restaurant):
    """A product match ("Tiene refresco") must not silently move someone who was ordering from one
    business to another: Sabi says which business has it and asks once."""
    contact=await memory.get(db,phone)
    topic=(contact.last_topic if contact else '') or ''
    if not topic.startswith('tu pedido en '):return ''
    same=f'tu pedido en {restaurant.name}'
    if topic==same or topic.startswith(same+' ('):return ''
    known=(await db.execute(select(Restaurant))).scalars().all()
    previous=max((r for r in known if topic==f'tu pedido en {r.name}' or topic.startswith(f'tu pedido en {r.name} (')),
                 key=lambda r:len(r.name),default=None)
    if not previous:return ''
    if re.search(r'\[sabi:',body,re.I) or await restaurant_by_mention(db,body):return ''
    # Both businesses are kept so the answer can pick one, and the request too when it fits whole:
    # a cut request (missing a time or an instruction) is never forwarded, the customer says it again.
    pending=f'{_SWITCH}{restaurant.id}>{previous.id}|'
    await memory.set_topic(db,phone,pending+(body if len(pending+body)<=80 else ''))
    return f'Eso lo encontré en *{restaurant.name}*. ¿Quieres pedirlo allí o seguimos con {previous.name}?'


async def _switch_answer(db,phone,body):
    """(restaurant, body) chosen by the reply to the switch question; (None, body) otherwise."""
    contact=await memory.get(db,phone)
    m=re.match(r'^cambio de local: (\d+)>(\d+)\|(.*)$',(contact.last_topic if contact else '') or '',re.S)
    if not m:return None,body
    offered,previous,asked=await db.get(Restaurant,int(m[1])),await db.get(Restaurant,int(m[2])),m[3]
    if offered and _YES.match(body):
        # A bare "Sí" carries the original request ("Tiene refresco") to the business offered.
        return offered,(body if not asked or re.search(r'\w{3,}',_YES.sub('',body,count=1)) else asked)
    if previous:
        await memory.set_topic(db,phone,f'tu pedido en {previous.name}')
        if _NO.match(body):return previous,body
    return None,body


async def _resolve(db: AsyncSession, phone: str, body: str):
    """(restaurant, body, reply). `reply` is Sabi's concierge text when no business is named
    (None when a plain welcome was already sent recently)."""
    if concierge.is_greeting(body):
        # A bare "hola" starts over: it must not stay inside the last business's open conversation.
        await _close_open_conversations(db, phone)
        text, _ = await concierge.reply(db, body, phone)
        return None, body, text
    unresolved=await _unresolved_place_reply(db,phone,body)
    if unresolved:return None,body,unresolved
    active=await focus.get(db,phone)
    if active and active.domain=='place' and active.city:
        mentioned=await restaurant_by_mention(db,body)
        if not mentioned or concierge._plain(mentioned.name)==concierge._plain(active.entity):
            return None,body,f'Mantengo tu consulta de {active.entity or "locales"} en {active.city}. No tengo opciones ni una sede verificadas allí; no usaré resultados de otra ciudad. ¿Tienes un enlace oficial de esa sede?'
    requested,unknown=concierge.cuisine_request(body)
    if (requested or unknown) and not await restaurant_by_mention(db,body):
        await memory.set_topic(db,phone,'comida')
        text,_=await concierge.reply(db,body,phone)
        return None,body,text
    # A full-catalog ask ("dame todos los restaurantes que tengas") is a concierge question,
    # never a message for the business of the open conversation.
    if concierge.wants_full_catalog(body) and not await restaurant_by_mention(db,body):
        text,_=await concierge.reply(db,body,phone)
        return None,body,text
    picked,picked_body=await _switch_answer(db,phone,body)
    restaurant, routed_body = (picked,picked_body) if picked else await restaurant_for_message(db, phone, body)
    if restaurant:
        switched=await _silent_business_switch(db,phone,body,restaurant)
        if switched:return None,body,switched
        # Keep what Sabi had just offered in the general chat: the business agent reads
        # the topic as context, so "Y nacional?" after a recommendation is not read in a void.
        contact=await memory.get(db,phone)
        previous=(contact.last_topic if contact else '') or ''
        topic=f"tu pedido en {restaurant.name}"
        if previous.startswith('recomendación de locales:'):
            topic=f"{topic} ({previous})"
        await memory.set_topic(db, phone, topic)
        previous=await focus.get(db,phone)
        named=named_business_query(body)
        said=named[1] if named else ''
        # A city written in this order, where the business registered delivery, is the task city.
        city=venezuela.canonical(said) if said and await venezuela.covers(db,restaurant,said) else ''
        if not city and previous and previous.domain=='restaurant' and previous.entity==restaurant.name:
            city=previous.city
        # A city asked for just before, where this business registered delivery, stays the task city.
        if not city and previous and previous.city and (previous.domain=='general' or (previous.domain=='place' and not previous.entity)) and await venezuela.covers(db,restaurant,previous.city):
            city=previous.city
        await focus.save(db,phone,domain='restaurant',entity=restaurant.name,city=city)
        return restaurant, routed_body, None
    active=await focus.get(db,phone)
    if active and active.domain=='place':
        return None,body,f'Mantengo tu consulta de {active.entity}'+(f' en {active.city}.' if active.city else '.')+' Aún no tengo una fuente verificada para su menú, horario o delivery. ¿Tienes su enlace oficial?'
    text, is_welcome = await concierge.reply(db, body, phone)
    if is_welcome:
        now = datetime.now(timezone.utc)
        last = _welcomed.get(phone)
        if last and now - last <= _WELCOME_COOLDOWN:
            return None, body, None
        _welcomed[phone] = now
    return None, body, text


async def _route_or_explain(db: AsyncSession, phone: str, body: str):
    restaurant, routed_body, reply = await _resolve(db, phone, body)
    if reply:
        await send_whatsapp_message(phone, reply)
    return restaurant, routed_body


async def _events_route(db: AsyncSession, phone: str, body: str, external_id: str | None = None,
                        profile_name: str = ""):
    """Events assistant channel. Returns the reply text, or None if the message is not for it."""
    reset_context=bool(re.search(r'\b(?:olvida|reinicia|borra) (?:el )?contexto\b',concierge._plain(body)))
    if memory.FORGET.search(body) or reset_context:
        if not reset_context:await memory.forget(db, phone)
        else:await memory.set_topic(db,phone,'general')
        await focus.forget(db,phone)
        from ..event_models import EventSession
        from ..cinema_whatsapp import session_id_for
        await db.execute(update(EventSession).where(EventSession.id==session_id_for(phone)).values(updated_at=datetime(1970,1,1)))
        await db.commit()
        await _close_open_conversations(db,phone)
        reply = ('Listo, dejé atrás la tarea anterior. Conservé tu nombre.' if reset_context else 'Listo, borré tu nombre guardado y la tarea activa. El historial de mensajes no se ha eliminado.')
        await send_whatsapp_message(phone, reply)
        return reply
    contact=await memory.note(db, phone, body, profile_name)
    # During a gym signup the booking flow owns the name question and its answer.
    _,gym_state=await gym_whatsapp._state(db,phone)
    gym_step=bool(gym_state.get('step'))
    said=''
    if memory.name_pending(contact) and not gym_step:
        # Only the reply right after "¿Cómo te llamas?" can be a bare name, and only a known first name.
        await memory.end_name_prompt(db,phone,contact)
        # "Soy Ana, ¿hay boxeo?" saves the name (memory.note) but is answered by the routes below.
        said=memory.bare_name(body) or (memory.extract_name(body) if len(body.split())<=4 and not re.search(r'[,;?]',body) else '')
        if said:await memory.set_name(db,phone,said)
    if said:
        reply=f'¡Mucho gusto, {memory.display_name(said)}! Ya me quedo con tu nombre. ¿En qué te ayudo?'
        await send_whatsapp_message(phone,reply)
        return reply
    name_reply='' if gym_step else memory.name_reply(contact,body)
    if name_reply:
        if name_reply.endswith(memory.ASK_NAME):await memory.ask_name(db,phone)
        await send_whatsapp_message(phone,name_reply)
        return name_reply
    # A new explicit domain outranks both unresolved-place and sticky sessions.
    text=concierge._plain(body).strip(' ¿?!.')
    active=await focus.get(db,phone)
    plc_question=bool(re.search(r'\bque hay para ver en plc\b',text))
    city_answer=re.sub(r'^(?:hola|alo|buenas)[, ]+', '',text)
    city_clarification=city_answer=='puerto la cruz' and active and active.domain=='cinema'
    if city_answer=='plc' and active and active.domain=='cinema' and active.entity=='awaiting_city':city_clarification=True
    if active and active.domain=='cinema' and re.search(r'\b(?:no entiendes|no me entiendes|no entendiste)\b',text):
        reply='Seguimos con la cartelera de cine'+(f' en {active.city}.' if active.city else '. ¿En qué ciudad quieres verla?')
        if active.city:reply+=' Aún necesito horarios verificados de esa ciudad; no he comprado entradas.'
        await send_whatsapp_message(phone,reply)
        return reply
    if concierge.is_greeting(body) and active and active.domain=='cinema':
        reply='Seguimos con cine'+(f' en {active.city}.' if active.city else '. ¿En qué ciudad te gustaría ver la cartelera?')
        await send_whatsapp_message(phone,reply)
        return reply
    location_reply=await focus.location_reply(db,phone,body)
    if location_reply:
        await send_whatsapp_message(phone,location_reply)
        return location_reply
    recommendation_city=concierge.recommendation_city(body)
    domain=concierge.explicit_recommendation_domain(body)
    negated=bool(re.search(r'\b(?:no|ni)\b',text))
    if negated and re.search(r'\b(cine|cines|comida|comer|peliculas?)\b',text):
        reply='¿Quieres seguir con cine, buscar comida o hacer otra consulta?'
        await send_whatsapp_message(phone,reply)
        return reply
    recommendation=concierge.ambiguous_recommendation(body)
    pending=active and active.domain=='general' and active.entity=='pending_recommendation_domain'
    target_city=recommendation_city or (active.city if pending else '')
    if target_city and (recommendation or domain) and not named_business_query(body):
        if domain=='cinema' or (not domain and active and active.domain=='cinema'):
            await focus.save(db,phone,domain='cinema',city=target_city)
            if await wants_cinema(db,phone,'cine'):
                return await handle_cinema_whatsapp(db,phone,body,external_id)
            reply=f'Seguimos con cine en {target_city}. No tengo una cartelera verificada disponible ahora.'
        elif domain=='food':
            await focus.save(db,phone,domain='general',entity='pending_recommendation_domain',city=target_city)
            reply=await venezuela.local_options(db,target_city,phone) or f'Buscas comida en {target_city}. Aún no tengo un filtro geográfico verificado para recomendarte locales allí. ¿Tienes un local o enlace oficial que quieras revisar?'
        else:
            await focus.save(db,phone,domain='general',entity='pending_recommendation_domain',city=target_city)
            reply=f'¿Buscas comida o un plan de cine en {target_city}?'
        await send_whatsapp_message(phone,reply)
        return reply
    if plc_question:
        await focus.save(db,phone,domain='cinema')
        reply='¿Con PLC te refieres a Puerto La Cruz para ver cine?'
        await send_whatsapp_message(phone,reply)
        return reply
    if explicit_cinema(body) or city_clarification:
        city='Puerto La Cruz' if city_clarification else (active.city if active and active.domain=='cinema' else '')
        await focus.save(db,phone,domain='cinema',city=city)
        cinema_body=body if not city_clarification else 'Cine en Puerto La Cruz'
        if await wants_cinema(db,phone,cinema_body):
            return await handle_cinema_whatsapp(db,phone,cinema_body,external_id)
        reply='La consulta ahora es de cine. No tengo una cartelera verificada disponible en este momento.'
        await send_whatsapp_message(phone,reply)
        return reply
    city_reply=await focus.city_reply(db,phone,body)
    if city_reply is not None:
        if city_reply:await send_whatsapp_message(phone,city_reply)
        return city_reply
    source_reply=await place_source.reply(db,phone,body)
    if source_reply is not None:
        if source_reply:await send_whatsapp_message(phone,source_reply)
        return source_reply
    unresolved=await _unresolved_place_reply(db,phone,body)
    if unresolved:
        await send_whatsapp_message(phone,unresolved)
        return unresolved
    place_reply=await focus.place_reply(db,phone,body)
    if place_reply:
        await send_whatsapp_message(phone,place_reply)
        return place_reply
    shopping_reply=await shopping_inquiry.reply(db,phone,body)
    if shopping_reply is not None:
        if shopping_reply:await send_whatsapp_message(phone,shopping_reply)
        return shopping_reply
    if explicit_cinema(body) and await wants_cinema(db, phone, body):
        return await handle_cinema_whatsapp(db, phone, body, external_id)
    if await gym_whatsapp.wants_gym(db, phone, body):
        return await gym_whatsapp.handle_gym_whatsapp(db, phone, body)
    if await wants_cinema(db, phone, body):
        return await handle_cinema_whatsapp(db, phone, body, external_id)
    if not await wants_events(db, phone, body):
        return None
    await memory.set_topic(db, phone, "entradas para eventos")
    return await handle_event_whatsapp(db, phone, body, external_id)


@router.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhook/whatsapp")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                phone = msg.get("from", "")
                body = msg.get("text", {}).get("body", "")
                name = ""
                for c in value.get("contacts", []):
                    if c.get("wa_id") == phone:
                        name = c.get("profile", {}).get("name", "")
                if phone and body:
                    if not await claim_inbound(db,'meta',digits(phone),msg.get('id'),platform_id=msg.get('id') or ''):
                        continue
                    await _react(phone, msg.get("id"), body)
                    if await _pilot_route(db, phone, body):
                        continue
                    if await _events_route(db, phone, body, msg.get("id"), name) is not None:
                        continue
                    restaurant, body = await _route_or_explain(db, phone, body)
                    if not restaurant:
                        continue
                    await handle_inbound_message(db, restaurant, phone, body, name,
                                                 external_id=msg.get("id"))
    return {"status": "ok"}


@router.post("/webhook/kapso")
async def receive_kapso(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    secret = settings.kapso_webhook_secret
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest() if secret else ""
    if not secret or not hmac.compare_digest(expected, request.headers.get("X-Webhook-Signature", "")):
        return Response(status_code=401)
    if request.headers.get("X-Webhook-Event") != "whatsapp.message.received":
        return {"status": "ignored"}
    data = json.loads(raw)
    for item in data.get("data", []) if data.get("batch") else [data]:
        msg = item.get("message") or {}
        conv = item.get("conversation") or {}
        if msg.get("type") != "text" or (msg.get("kapso") or {}).get("direction", "inbound") != "inbound":
            continue
        phone = msg.get("from") or conv.get("phone_number") or ""
        body = (msg.get("text") or {}).get("body", "")
        if phone and body:
            if not await claim_inbound(db,'kapso',digits(phone),msg.get('id')):
                continue
            await _react(phone, msg.get("id"), body)
            if await _pilot_route(db, phone, body):
                continue
            if await _events_route(db, phone, body, msg.get("id"), conv.get("contact_name") or "") is not None:
                continue
            restaurant, body = await _route_or_explain(db, phone, body)
            if not restaurant:
                continue
            await handle_inbound_message(db, restaurant, phone, body, conv.get("contact_name") or "",
                                         external_id=msg.get("id"))
    return {"status": "ok"}


# Local simulator: same pipeline without Meta's payload envelope.
@router.post("/webhook/simulate")
async def simulate_message(body_in: dict, db: AsyncSession = Depends(get_db)):
    if await recent_inbound_count(db) >= settings.simulate_limit_hour:
        return {"reply": "La demo recibió muchos mensajes en la última hora. Prueba de nuevo más tarde."}
    phone = body_in.get("phone", "59912345678")
    text = body_in.get("text", "")
    name = body_in.get("name", "Cliente Test")
    events_reply = await _events_route(db, phone, text, None, name)
    if events_reply is not None:
        return {"reply": events_reply}
    restaurant, text, concierge_reply = await _resolve(db, phone, text)
    if not restaurant:
        return {"reply": concierge_reply or WELCOME_MESSAGE}
    reply = await handle_inbound_message(db, restaurant, phone, text, name)
    return {"reply": reply}


@router.post("/webhook/zernio")
async def receive_zernio(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    secret = settings.zernio_webhook_secret
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest() if secret else ""
    if not secret or not hmac.compare_digest(expected, request.headers.get("X-Zernio-Signature", "")):
        return Response(status_code=401)
    data = json.loads(raw)
    if data.get("event") != "message.received":
        return {"status": "ignored"}
    msg = data.get("message") or {}
    sender = msg.get("sender") or {}
    if (msg.get("direction") != "incoming" or msg.get("platform") != "whatsapp"
            or (data.get("metadata") or {}).get("standby")):
        return {"status": "ignored"}
    phone = digits(sender.get("phoneNumber") or sender.get("id") or "")
    body = msg.get("text") or ""
    if msg.get("conversationId"):
        zernio_conversations[phone] = msg["conversationId"]
    external_id = msg.get("platformMessageId") or msg.get("id")
    if not phone or not body:
        return {'status':'ignored'}
    if not await claim_inbound(db,'zernio',phone,msg.get('id'),platform_id=msg.get('platformMessageId') or ''):
        return {'status':'duplicate_or_unidentified'}
    await send_whatsapp_typing(phone)
    # Claim occurs before reaction, quote context or any route side effect.
    # Use only the WhatsApp platform ID for quote replies, not Zernio's internal id.
    with incoming_reply_context(phone, msg.get("platformMessageId") or ""):
        if settings.zernio_native_reactions:
            await _react(phone, external_id, body)
        if phone and body and await _pilot_route(db, phone, body):
            return {"status": "ok"}
        if phone and body and await _events_route(db, phone, body, external_id, sender.get("name") or "") is not None:
            return {"status": "ok"}
        restaurant, body = await _route_or_explain(db, phone, body)
        if not (restaurant and phone and body):
            return {"status": "ignored"}
        await handle_inbound_message(db, restaurant, phone, body, sender.get("name") or "",
                                     external_id=msg.get("platformMessageId") or msg.get("id"))
        return {"status": "ok"}
