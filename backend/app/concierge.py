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
from . import memory, venezuela
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


_REJECTED_DOMAIN = re.compile(
    r"\b(?:no|ni)\s+(?:quiero\s+|busco\s+|me\s+interesa\s+)?(?:ir\s+al\s+|ver\s+|el\s+|la\s+)?"
    r"(?:cine|cines|comida|comer|peliculas?)\b"
    r"|\b(?:cine|cines|comida|peliculas?)\s+no\b")


def rejects_domain(body: str) -> bool:
    """"No quiero comida", "ni cine": the customer turns a topic down. A "no" about something else
    ("solo información, no hagas pedidos", "no compres entradas") is not one."""
    return bool(_REJECTED_DOMAIN.search(_plain(body)))


def wants_food(body: str) -> bool:
    return bool(FOOD_INTENT.search(_plain(body)))


CUISINES={
    'china':('chin[ao]s?',), 'italiana':('italian[ao]s?',),
    'japonesa':('japones(?:a|as|es)?','sushi'), 'mexicana':('mexican[ao]s?',),
    'arabe':('arabes?',), 'venezolana':('venezolan[ao]s?',),
    'peruana':('peruan[ao]s?',),'india':('hind[uú]','india'),
    'tailandesa':('tailandes(?:a|as|es)?',),'criolla':('crioll[ao]s?',)}

DISHES={'pizza':('pizzas?','pizzerias?'),'hamburguesas':('hamburguesas?','burgers?'),
        'arepas':('arepas?',),'empanadas':('empanadas?',),'parrilla':('parrillas?',)}


def food_kind(body):
    """The dish or cuisine a food follow-up names ("¿Y pizza?" -> pizza), or ''."""
    text=_plain(body)
    for name,patterns in {**DISHES,**CUISINES}.items():
        if any(re.search(r'\b'+p+r'\b',text) for p in patterns):return name
    return ''


async def _serves(db,restaurant,kind):
    patterns={**DISHES,**CUISINES}[kind]
    exact=re.compile(r'\b(?:'+'|'.join(patterns)+r')\b')
    if exact.search(_plain(restaurant.tagline or '')):return True
    lead=re.compile(r'^(?:'+'|'.join(patterns)+r')\b')
    items=(await db.execute(select(MenuItem).where(MenuItem.restaurant_id==restaurant.id,MenuItem.available.is_(True)))).scalars().all()
    return any(lead.match(_plain(m.name).strip()) or exact.fullmatch(_plain(m.category or '').strip()) for m in items)


async def food_in_city(db,phone,city,kind=''):
    """Food asked for in one city. The city and the dish stay the task until the customer
    changes one ("¿Y pizza?" keeps the city, "Mejor en Lechería" keeps the pizza)."""
    from . import conversation_focus as focus
    name=venezuela.canonical(city)
    if phone:await focus.save(db,phone,domain='general',entity='food'+(':'+kind if kind else ''),city=name)
    label=('comida '+kind if kind in CUISINES else kind)
    hits=[r for r,_ in await venezuela.covering(db,name)]
    matching=[r for r in hits if await _serves(db,r,kind)] if kind else hits
    if matching:return await venezuela.local_options(db,name,phone,only=matching)
    if not hits:
        return (f'En {name} no tengo locales'+(f' de {label}' if kind else '')+' verificados. '
                'No voy a usar opciones de otra ciudad. ¿Tienes un local o enlace oficial de allí que quieras revisar?')
    return (f'En {name} no tengo locales de {label} verificados. Sí te puedo atender allí con:\n'
            +'\n'.join(f'• *{r.name}*' for r in hits)+'\n\n¿Quieres ver el menú de alguno?')


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
            if venezuela.find_city(value) or not re.search(r'\b(casa|mi|el|la|esa|esta|mensajes|partes|lista|tabla|ingles|espanol)\b',_plain(value)):
                return venezuela.canonical(value)
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


LIST_ALL = re.compile(r"\b(todos|todas|complet[ao]s?|cu[aá]les|lista)\b")
CATALOG_WORD = re.compile(r"\b(restaurantes?|locales|sitios|lugares|opciones|cat[aá]logo)\b")


def wants_full_catalog(body: str) -> bool:
    """"Dame todos los restaurantes que tengas": the person asked for the whole catalog,
    not a suggestion. The full list is always answered in stable order, never sampled."""
    text = _plain(body)
    return bool(LIST_ALL.search(text) and CATALOG_WORD.search(text))


async def recommendations(db: AsyncSession, pick: int = 2, body: str = "", phone: str = "") -> str:
    """One or two suggestions, not the whole list; varied between asks. Internal test
    businesses ("Prueba ...") are never recommended. A full-catalog request returns
    every business, in stable order. When a phone is given, the offered names are
    remembered as the current topic so a later handoff to a business can see them."""
    city=recommendation_city(body)
    if city:
        if venezuela.find_city(city):return await food_in_city(db,phone,city,food_kind(body))
        local=await venezuela.local_options(db,city,phone)
        if local:return local
        return f'Buscas comida en {city}. No tengo un filtro geográfico verificado para recomendarte locales allí. ¿Tienes un local o enlace oficial que quieras revisar?'
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
    chosen = list(rows) if wants_full_catalog(body) else random.sample(rows, min(pick, len(rows)))
    if phone and chosen:
        await memory.set_topic(db, phone, "recomendación de locales: " + ", ".join(r.name for r in chosen))
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
    if rejects_domain(body):
        return '¿Quieres seguir con cine, buscar comida o hacer otra consulta?',False
    if ambiguous_recommendation(body):
        city=recommendation_city(body)
        return '¿Buscas comida o un plan de cine'+(f' en {city}' if city else '')+'?',False
    requested,unknown=cuisine_request(body)
    if requested or unknown or re.search(r'\bitalian[ao]s?\b',_plain(body)):
        return await recommendations(db,body=body,phone=phone), False
    sellers = await restaurants_by_product(db, body)
    if len(sellers) >= 2:
        names = "\n".join(f"• *{r.name}*" for r in sellers[:4])
        return ("¡Claro! 😋 Eso lo consigues en:\n" + names +
                f"\n\nDime dónde y te lo armo, por ejemplo «quiero pedir en {sellers[0].name}».", False)
    if wants_food(body):
        text = await recommendations(db,body=body,phone=phone)
        return text, False
    returning = bool(contact and contact.last_topic)
    if phone and not name:
        # Without a usable name (none saved, or one that is not a name) Sabi asks for it, so every
        # later greeting can use it. A stored value is never changed here.
        await memory.ask_name(db, phone)
        return ("Hola de nuevo." if returning else "¡Hola! 👋 Soy Sabi.") + " " + memory.ASK_NAME, True
    return await _hello(db, name, returning), True
