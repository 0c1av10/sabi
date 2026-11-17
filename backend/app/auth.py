from fastapi import Depends, HTTPException, Request
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from itsdangerous import URLSafeSerializer, BadSignature

from .config import settings
from .db import get_db
from .models import Conversation, Customer, MenuItem, Restaurant

_serializer = URLSafeSerializer(settings.session_secret, salt="sabi-auth")
COOKIE_NAME = "sabi_session"


def make_token(restaurant_id: int) -> str:
    return _serializer.dumps({"rid": restaurant_id})


def parse_token(token: str) -> int | None:
    try:
        return _serializer.loads(token).get("rid")
    except BadSignature:
        return None


async def current_restaurant(request: Request, db: AsyncSession = Depends(get_db)) -> Restaurant:
    token = request.cookies.get(COOKIE_NAME) or request.headers.get("X-Sabi-Token", "")
    rid = parse_token(token) if token else None
    if rid is None:
        raise HTTPException(401, "No autenticado")
    restaurant = await db.get(Restaurant, rid)
    if not restaurant:
        raise HTTPException(401, "Restaurante no encontrado")
    return restaurant


async def restaurant_for_webhook(db: AsyncSession) -> Restaurant:
    """MVP: single WhatsApp number = single restaurant (first one). Extend by
    mapping phone_number_id -> restaurant when multi-tenant."""
    return (await db.execute(select(Restaurant))).scalars().first()


_GENERIC = {"restaurante", "restaurant", "resto", "bar", "cafe", "cafeteria", "el", "la", "los",
            "las", "de", "del", "y", "&"}


def _norm(text: str) -> list[str]:
    plain = unicodedata.normalize("NFD", text.lower())
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", plain)


async def restaurant_by_mention(db: AsyncSession, body: str) -> Restaurant | None:
    """A first message such as "hola, quiero pedir en Nacional" names the business.
    Matches when every distinctive word of the name (or the slug) appears in the message;
    the longest match wins and a tie is treated as ambiguous (no routing)."""
    words = set(_norm(body))
    if not words:
        return None
    best: list[tuple[int, Restaurant]] = []
    for r in (await db.execute(select(Restaurant))).scalars().all():
        for candidate in (_norm(r.name), _norm(r.slug)):
            core = [w for w in candidate if w not in _GENERIC]
            if core and (all(w in words for w in core) or (len(core) > 1 and "".join(core) in words)):
                best.append((len(core), r))
                break
    if not best:
        return None
    top = max(n for n, _ in best)
    winners = [r for n, r in best if n == top]
    return winners[0] if len(winners) == 1 else None


_PRODUCT_STOP = {"quiero", "unos", "unas", "pedir", "para", "compartir", "piezas", "pieza", "pzas", "individual",
                 "combo", "combos", "natural", "casero", "entero", "medio", "platos", "entradas", "postres",
                 "bebidas", "general", "algo", "hola", "buenas", "favor", "necesito", "gustaria", "tienen",
                 "tiene", "hay", "unos", "dame", "mandame", "ordenar", "comprar", "ocupo", "busco", "mucho"}


def _stem(word: str) -> str:
    for suffix in ("es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _same(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 6 and (a.startswith(b) or b.startswith(a)))


def response_format_request(body: str) -> bool:
    """Presentation instructions refer to the current answer, not a new merchant.

    Recognize a command plus a formatting target; do not globally ban ordinary
    merchant names containing words such as Mensajes or Letras.
    """
    text=' '.join(_norm(body))
    command=re.match(r'^(?:por favor )?(?:mandamelo|enviamelo|pasamelo|damelo|dimelo|muestramelo|mandame|enviame|pasame|dame|dime|muestra|muestrame|divide|dividelo|separa|separalo|resume|resumelo|ponlo|hazlo|escribelo|puedes (?:mandarlo|enviarlo|pasarlo|dividirlo|resumirlo))\b',text)
    target=re.search(r'\b(?:mensajes?|partes?|parrafos?|lineas?|palabras?|lista|tabla|resumen|detalle|detallado|corto|breve|viñetas|vinetas|puntos|mayusculas|minusculas|ingles|espanol)\b',text)
    return bool(command and target)


def named_business_query(body: str) -> tuple[str,str] | None:
    """Conservative explicit place references, not an inferred city or product match."""
    if response_format_request(body):return None
    text=body.strip().strip('¿?!. ')
    # City is a location qualifier, never positive product/tenant evidence.
    explicit_visit=re.search(r'\b(?:pedir|comer|cenar|almorzar|ir)\s+(?:en|a|al)\s+(.+)$',text,re.I)
    if explicit_visit:text=explicit_visit[1]
    city_match=re.search(r'\s+en\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]+)$',text,re.I)
    city=city_match[1].strip() if city_match else ''
    head=text[:city_match.start()].strip() if city_match else text
    prefix=re.match(r'^(?:hola[, ]+)?(?:(?:que|qué) sabes de|sabes de|conoces|sobre|de|del|y de)\s+(?:(?:el|la)\s+)?(?:(?:restaurante|pizzer[ií]a|local|caf[eé])\s+)?(.+)$',head,re.I)
    business_word=re.search(r'\b(?:restaurante|pizzer[ií]a|caf[eé]|local)\s+(.+)$',head,re.I)
    candidate=(prefix or business_word)
    if candidate:entity=candidate[1].strip()
    elif (city or explicit_visit) and len(head.split())<=4:entity=head
    else:return None
    # These identify an order/food task, not a named place.
    food={'delivery','retiro','pedido','comida','cocina','pizza','pizzas','pastelitos','cachapa','cachapas','sushi','pollo','cine','cines','pelicula','peliculas','evento','entradas','laptop','taxi','viaje','direccion','precio','horario'}
    words=_norm(entity)
    if not words or len(words)>5 or any(w in food for w in words):return None
    if words[0] in {'hola','busca','buscame','dime','me','nos','cuentame','recomienda','recomiendame','quiero','tengo','necesito','mandame','mandamelo','enviamelo','pasamelo','dimelo','damelo','muestramelo','dividelo','separalo','resumelo','ponlo','hazlo','escribelo','una','un','dos','tres','para','cuanto','cuantos','hay','tienen','que','cuando','residencias','avenida','calle'}:return None
    if re.search(r'[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9 &\'-]',entity):return None
    return entity[:100],city[:100]


async def restaurants_by_product(db: AsyncSession, body: str) -> list[Restaurant]:
    """Businesses that sell what the message asks for ("quiero unos pastelitos", "quiero pizza").
    Only distinctive words count (4+ letters, not filler). A word that is the category or the first
    word of a product name (Pizzas, Pastelitos) outweighs one that is only a flavor inside another
    product ("Pastelito de Pizza"), so only the best-matching businesses are returned."""
    product_body=re.split(r'\s+en\s+',body,flags=re.I)[0]
    wanted = {_stem(w) for w in _norm(product_body) if len(w) >= 4 and w not in _PRODUCT_STOP}
    if not wanted:
        return []
    best: dict[int, tuple[int, Restaurant]] = {}
    rows = (await db.execute(select(MenuItem, Restaurant).join(
        Restaurant, MenuItem.restaurant_id == Restaurant.id).where(MenuItem.available.is_(True)))).all()
    for item, rest in rows:
        category = {_stem(w) for w in _norm(item.category or "") if len(w) >= 4 and w not in _PRODUCT_STOP}
        name_words = [_stem(w) for w in _norm(item.name or "") if len(w) >= 4 and w not in _PRODUCT_STOP]
        score = 0
        for w in wanted:
            if any(_same(w, c) for c in category):
                score = max(score, 3)
            if name_words and _same(w, name_words[0]):
                score = max(score, 2)
            if any(_same(w, n) for n in name_words):
                score = max(score, 1)
        if score and score > best.get(rest.id, (0, rest))[0]:
            best[rest.id] = (score, rest)
    if not best:
        return []
    top = max(sc for sc, _ in best.values())
    if top<2:return []  # A flavor or city suffix alone cannot choose a merchant.
    return [r for sc, r in best.values() if sc == top]


async def restaurant_for_message(db: AsyncSession, phone: str, body: str) -> tuple[Restaurant | None, str]:
    """Resolve a shared WhatsApp message to a tenant.

    Click-to-WhatsApp links include ``[sabi:<slug>]``. Once a conversation is
    open, subsequent messages stay with that restaurant even without the tag.
    """
    match = re.search(r"\[sabi:([a-z0-9-]+)\]", body.lower())
    if match:
        restaurant = (await db.execute(
            select(Restaurant).where(Restaurant.slug == match.group(1))
        )).scalar_one_or_none()
        if restaurant:
            return restaurant, re.sub(r"\s*\[sabi:[a-z0-9-]+\]\s*", " ", body, flags=re.I).strip()

    named=named_business_query(body)
    mentioned = await restaurant_by_mention(db,named[0] if named else body)
    if mentioned:
        return mentioned, body

    # Unknown explicit entity must not inherit an unrelated open restaurant.
    if named_business_query(body) or re.search(r'https?://',body,re.I):return None,body
    from . import conversation_focus
    active=await conversation_focus.get(db,phone)
    restaurant = (await db.execute(
        select(Restaurant)
        .join(Customer, Customer.restaurant_id == Restaurant.id)
        .join(Conversation, Conversation.customer_id == Customer.id)
        .where(Customer.phone == phone, Conversation.status == "open")
        .order_by(Conversation.updated_at.desc())
    )).scalars().first()
    if restaurant and active and active.domain=='restaurant' and active.entity==restaurant.name:
        return restaurant, body
    if active and active.domain=='place':return None,body
    # No business named and no open conversation: a product only one business sells decides it.
    by_product = await restaurants_by_product(db, body)
    if len(by_product) == 1:
        return by_product[0], body
    return None, body
