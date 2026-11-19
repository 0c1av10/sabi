"""Sabi's reply when a message names no business: a friendly concierge that recommends.

Sabi is one assistant for many businesses, so it never introduces itself as the assistant of a
particular restaurant or producer. It chats naturally and, when asked about food or delivery,
recommends the places it knows; tickets are handled by the events assistant.
"""
import random
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import restaurants_by_product
from . import memory
from .models import Restaurant, MenuItem

WELCOME = (
    "¡Hola! 👋 Soy Sabi. Te echo una mano con lo que necesites: dónde comer o pedir delivery, "
    "conseguir entradas para un evento o reservar tu clase de boxeo. ¿Qué se te antoja hoy?"
)

FOOD_INTENT = re.compile(
    r"\b(comer|comida|comidita|cenar|cena|almorzar|almuerzo|desayun\w*|hambre|hambriento|antoj\w*|"
    r"restaurante\w*|restaurant|delivery|domicilio|pedir|pedido|pizza|hamburguesa\w*|parrilla|"
    r"sitio\w* para|lugar\w* para|donde (?:comer|cenar|almorzar)|provoca)\b")


def _plain(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def wants_food(body: str) -> bool:
    return bool(FOOD_INTENT.search(_plain(body)))


CUISINES={
    'china':('chin[ao]s?',), 'italiana':('italian[ao]s?',),
    'japonesa':('japones(?:a|as|es)?','sushi'), 'mexicana':('mexican[ao]s?',),
    'arabe':('arabes?',), 'venezolana':('venezolan[ao]s?',),
    'peruana':('peruan[ao]s?',),'india':('hind[uú]','india'),
    'tailandesa':('tailandes(?:a|as|es)?',),'criolla':('crioll[ao]s?',)}

def cuisine_request(body):
    text=_plain(body)
    hits=[name for name,patterns in CUISINES.items() if any(re.search(r'\b'+p+r'\b',text) for p in patterns)]
    if len(hits)>1 or (hits and re.search(r'\b(?:no quiero|menos|excepto|sin)\b',text)):
        return '',True  # Multiple or negated restrictions need clarification, not a random pick.
    if hits:return hits[0],False
    m=re.search(r'\b(?:comida|cocina)\s+(?:de\s+)?([a-z]+)\b',text)
    if not m:return '',False
    if m[1] in {'rica','sabrosa','buena','deliciosa','rapida','casera','barata','economica','saludable'}:return '',False
    return '',True


def recommendation_city(body):
    original=body.strip(' ¿?!.')
    text=_plain(original)
    # Location is a query qualifier, never verified coverage. Preserve spelling.
    patterns=[r'^en\s+([a-z ]{2,60}?)[, ]+(?:que|cual|donde|recomiend\w*|busco|quiero|hay)\b',
              r'\ben\s+([a-z ]{2,60}?)(?:[,.!?]|$)']
    for pattern in patterns:
        match=re.search(pattern,text)
        if match:
            value=original[match.start(1):match.end(1)].strip().strip(',').title()
            if not re.search(r'\b(casa|mi|el|la|mensajes|partes|lista|tabla|ingles|espanol)\b',_plain(value)):
                return value
    return ''


def explicit_recommendation_domain(body):
    text=_plain(body)
    if re.search(r'\b(?:no|ni)\b',text):return ''
    cinema=bool(re.search(r'\b(cine|cines|peliculas?|cartelera)\b',text))
    food=wants_food(body)
    if cinema==food:return ''
    return 'cinema' if cinema else 'food'


def ambiguous_recommendation(body):
    requested,unknown=cuisine_request(body)
    return bool(re.search(r'\brecomiend\w*\b',_plain(body))) and not wants_food(body) and not (requested or unknown)


async def recommendations(db: AsyncSession, pick: int = 2, body: str = "") -> str:
    """One or two suggestions, not the whole list; varied between asks. Internal test
    businesses ("Prueba ...") are never recommended."""
    city=recommendation_city(body)
    if city:return f'Buscas comida en {city}. No tengo un filtro geográfico verificado para recomendarte locales allí. ¿Tienes un local o enlace oficial que quieras revisar?'
    rows = (await db.execute(select(Restaurant).where(~Restaurant.name.ilike("prueba%"))
                             .order_by(Restaurant.id))).scalars().all()
    if not rows:
        requested,unknown=cuisine_request(body)
        if requested or unknown:return "No tengo opciones verificadas que coincidan con esa cocina en el catálogo actual. La búsqueda web automática aún no está conectada."
        return ("Todavía no tengo locales para recomendarte por aquí, pero cuéntame qué se te antoja "
                "y lo tengo en cuenta. 😊 Si buscas entradas para un evento, dímelo y te ayudo.")
    # Cuisine requests must match verified available menu evidence, never random cuisine.
    if re.search(r'\bitalian[ao]s?\b',_plain(body)):
        menus=(await db.execute(select(MenuItem).where(MenuItem.available.is_(True)))).scalars().all()
        italian_ids={m.restaurant_id for m in menus if (re.fullmatch(r'(pizzas?|pastas?|risottos?|ravioli|lasagna|lasana|gnocchi|panini)',_plain(m.category or '').strip()) or re.match(r'^(pizza|pasta|risotto|ravioli|lasagna|lasana|gnocchi|panini)\b',_plain(m.name).strip()))}
        rows=[r for r in rows if r.id in italian_ids]
        if not rows:return 'No tengo un menú italiano verificado en el catálogo actual. No te voy a recomendar otro tipo de comida como si fuera italiana.'
    requested,unknown=cuisine_request(body)
    if unknown:return '¿Qué tipo de cocina te gustaría? No tengo clara esa preferencia y prefiero no sustituirla por otra.'
    if requested and requested!='italiana':
        exact=re.compile(r'\b(?:'+ '|'.join(CUISINES[requested])+r')\b')
        rows=[r for r in rows if exact.search(_plain(r.tagline or ''))]
        if not rows:return f'No tengo un local de comida {requested} verificado en el catálogo actual. No te voy a recomendar otro tipo de comida como si coincidiera. La búsqueda web automática aún no está conectada.'
    chosen = random.sample(rows, min(pick, len(rows)))
    lines = []
    for r in chosen:
        tag = ""  # A catalog tagline is not verified geographic or service coverage.
        lines.append(f"• *{r.name}*" + (f" — {tag}" if tag else ""))
    return ("Estas son opciones del catálogo actual, sin confirmar su ubicación ni disponibilidad para tu zona:\n" + "\n".join(lines) +
            "\n\n¿Qué local te gustaría consultar?")


GREETING = re.compile(
    r"^\W*(?:hola+|holi+|buenas|buen\s?dia|buenos\s?dias|buenas\s?(?:tardes|noches)|hey|hi|saludos|inicio|"
    r"menu|opciones|ayuda|que\s+(?:tienes|tienen|hay|ofreces|ofrecen)|en\s+que\s+me\s+ayudas)"
    r"(?:\s+(?:sabi|a\s+todos|amigo|amiga))?\W*$")


def is_greeting(body: str) -> bool:
    """A bare "hola" / "buenas" / "menú": it restarts the conversation with Sabi's options."""
    return bool(GREETING.match(_plain(body).strip()))


async def _hello(db: AsyncSession, name: str, returning: bool) -> str:
    """Short on purpose: Sabi answers the greeting and lets the person say what they want;
    food, events or classes are then handled by what they write."""
    reliable=memory.extract_name("Me llamo "+name) if name else ""
    who = f", {reliable}" if reliable else ""
    if returning:
        return f"Hola de nuevo{who}. ¿Cómo te puedo ayudar hoy? ¿Quieres comer o se te antoja ir al cine?"
    return f"¡Hola{who}! 👋 Soy Sabi. ¿En qué te echo una mano hoy?"


async def reply(db: AsyncSession, body: str, phone: str = "") -> tuple[str, bool]:
    """(text, is_plain_welcome). The welcome is rate-limited by the caller; recommendations are not."""
    if _plain(body).strip(' ¡!¿?.,')=='sabi':return 'Aquí estoy. ¿En qué te ayudo?',False
    contact = await memory.get(db, phone) if phone else None
    candidate=memory.display_name(contact.name if contact else None)
    name=memory.extract_name("Me llamo "+candidate) if candidate else ""
    said = memory.extract_name(body)
    if said and len(body.split()) <= 6:
        return (f"¡Mucho gusto, {memory.display_name(said)}! 😊 Ya me quedo con tu nombre. "
                "¿Qué se te antoja hoy: comida, entradas o una clase de boxeo?"), False
    if re.search(r'\b(?:no|ni)\b',_plain(body)) and re.search(r'\b(cine|cines|comida|comer|peliculas?)\b',_plain(body)):
        return '¿Quieres seguir con cine, buscar comida o hacer otra consulta?',False
    if ambiguous_recommendation(body):
        city=recommendation_city(body)
        return '¿Buscas comida o un plan de cine'+(f' en {city}' if city else '')+'?',False
    requested,unknown=cuisine_request(body)
    if requested or unknown or re.search(r'\bitalian[ao]s?\b',_plain(body)):
        return await recommendations(db,body=body), False
    sellers = await restaurants_by_product(db, body)
    if len(sellers) >= 2:
        names = "\n".join(f"• *{r.name}*" for r in sellers[:4])
        return ("¡Claro! 😋 Eso lo consigues en:\n" + names +
                f"\n\nDime dónde y te lo armo, por ejemplo «quiero pedir en {sellers[0].name}».", False)
    if wants_food(body):
        text = await recommendations(db,body=body)
        return text, False
    return await _hello(db, name, bool(contact and contact.last_topic)), True
