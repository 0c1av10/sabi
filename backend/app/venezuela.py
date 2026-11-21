"""Venezuelan city knowledge and merchant-declared coverage.

The gazetteer only names places: it recognizes a city however people write it on WhatsApp
("lecheria", "PLC", "Ccs", "Pto Ordaz") and returns its canonical name and state. It never
says a business serves a city. Coverage comes only from the delivery zones a merchant
registered in the panel, so a city with no such zone keeps the "no verified filter" reply.
"""
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select


@dataclass(frozen=True)
class City:
    name: str
    state: str
    aliases: tuple[str, ...] = ()


# State capitals first, then other cities people commonly name. Aliases are written as people
# type them; matching ignores case and accents.
CITIES = (
    City("Caracas", "Distrito Capital", ("ccs",)),
    City("Puerto Ayacucho", "Amazonas", ("pto ayacucho",)),
    City("Barcelona", "Anzoátegui", ("bna",)),
    City("San Fernando de Apure", "Apure", ("san fernando",)),
    City("Maracay", "Aragua", ("mcy",)),
    City("Barinas", "Barinas"),
    City("Ciudad Bolívar", "Bolívar", ("cdad bolivar", "cd bolivar")),
    City("Valencia", "Carabobo", ("vlc",)),
    City("San Carlos", "Cojedes"),
    City("Tucupita", "Delta Amacuro"),
    City("Coro", "Falcón", ("santa ana de coro",)),
    City("San Juan de los Morros", "Guárico"),
    City("La Guaira", "La Guaira"),
    City("Barquisimeto", "Lara", ("bqto",)),
    City("Mérida", "Mérida"),
    City("Los Teques", "Miranda"),
    City("Maturín", "Monagas"),
    City("La Asunción", "Nueva Esparta"),
    City("Guanare", "Portuguesa"),
    City("Cumaná", "Sucre"),
    City("San Cristóbal", "Táchira"),
    City("Trujillo", "Trujillo"),
    City("San Felipe", "Yaracuy"),
    City("Maracaibo", "Zulia", ("mcbo",)),
    # Anzoátegui north coast, where the current merchants deliver.
    City("Lechería", "Anzoátegui", ("lecheria",)),
    City("Puerto La Cruz", "Anzoátegui", ("plc", "pto la cruz", "puerto la cruz")),
    City("Guanta", "Anzoátegui"),
    City("El Tigre", "Anzoátegui"),
    City("Anaco", "Anzoátegui"),
    City("Puerto Píritu", "Anzoátegui", ("pto piritu",)),
    # Other frequently named cities.
    # Puerto Ordaz and San Félix are separate delivery areas; "Ciudad Guayana" names neither.
    City("Ciudad Guayana", "Bolívar", ("guayana",)),
    City("Puerto Ordaz", "Bolívar", ("pto ordaz",)),
    City("San Félix", "Bolívar"),
    City("Upata", "Bolívar"),
    City("Puerto Cabello", "Carabobo", ("pto cabello",)),
    City("Naguanagua", "Carabobo"),
    City("San Diego", "Carabobo"),
    City("Guacara", "Carabobo"),
    City("Punto Fijo", "Falcón", ("pto fijo",)),
    City("Tucacas", "Falcón"),
    City("Calabozo", "Guárico"),
    City("Valle de la Pascua", "Guárico"),
    City("Carora", "Lara"),
    City("Cabudare", "Lara"),
    City("El Vigía", "Mérida"),
    City("Guarenas", "Miranda"),
    City("Guatire", "Miranda"),
    City("Charallave", "Miranda"),
    City("Higuerote", "Miranda"),
    City("Porlamar", "Nueva Esparta"),
    City("Pampatar", "Nueva Esparta"),
    City("Juan Griego", "Nueva Esparta"),
    City("Isla de Margarita", "Nueva Esparta", ("margarita", "la isla de margarita")),
    City("Acarigua", "Portuguesa"),
    City("Araure", "Portuguesa"),
    City("Carúpano", "Sucre"),
    City("San Antonio del Táchira", "Táchira"),
    City("Valera", "Trujillo"),
    City("Maiquetía", "La Guaira"),
    City("Catia La Mar", "La Guaira"),
    City("La Victoria", "Aragua"),
    City("Turmero", "Aragua"),
    City("Cagua", "Aragua"),
    City("Cabimas", "Zulia"),
    City("Ciudad Ojeda", "Zulia"),
)


def plain(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


_INDEX: dict[str, City] = {}
for _city in CITIES:
    for _key in (_city.name, *_city.aliases):
        _INDEX.setdefault(plain(_key), _city)
# "Centro de X" is a downtown zone, not all of X, so it is never read as the whole city.
_PREFIX = re.compile(r"^(?:la ciudad de|ciudad de)\s+")
_SCAN = re.compile(r"(?<![a-z0-9])(" + "|".join(sorted(map(re.escape, _INDEX), key=len, reverse=True)) + r")(?![a-z0-9])")


def find_city(value: str) -> City | None:
    """The Venezuelan city that `value` names as a whole ("lecheria", "PLC", "Caracas, Venezuela")."""
    key = plain(value)
    key = re.sub(r"\s+(?:venezuela|vzla|vnzla)$", "", key)
    key = _PREFIX.sub("", key)
    return _INDEX.get(key)


def cities_in(text: str) -> list[City]:
    """Every city named inside longer text ("Ciudad Guayana, Pto Ordaz", "delivery a PLC")."""
    return [_INDEX[m[1]] for m in _SCAN.finditer(plain(text))]


def canonical(value: str) -> str:
    """Canonical spelling of a known city; anything else is returned as given."""
    city = find_city(value)
    return city.name if city else value


_WHERE = re.compile(r"\b(?:en\s+)?(?:qu[eé]|cu[aá]l)\s+ciudad\s+(?:queda|est[aá]|es|son|se\s+encuentra)n?\b|\bd[oó]nde\s+(?:queda|est[aá]|se\s+ubica|se\s+encuentra)n?\b", re.I)
_SUBJECT_FILLER = {"el", "la", "los", "las", "de", "del", "y", "ese", "esa", "eso", "esos", "esas", "este", "esta", "esto", "estos", "estas", "local", "restaurante", "sede",
                   "exactamente", "ahora", "entonces", "eso", "me", "sabes", "oye", "por", "favor", "mismo", "dime"}


def asks_location(text: str) -> bool:
    """"¿En qué ciudad queda?" asks where a business is; it never names a city."""
    return bool(_WHERE.search(text or ""))


def location_subject(text: str) -> str:
    """What a location question asks about, "" when it refers back ("¿En qué ciudad queda?")."""
    rest = plain(_WHERE.sub(" ", text or ""))
    return " ".join(w for w in rest.split() if w not in _SUBJECT_FILLER)


def where_reply(restaurant) -> str:
    """Where a catalog business works, only from the delivery zones it registered."""
    from .delivery import zones_of
    names = [z["name"] for z in zones_of(restaurant)]
    if not names:
        return f"No tengo la ubicación de {restaurant.name}."
    where = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]
    return f"{restaurant.name} hace delivery a {where}. No tengo su dirección exacta."


async def covering(db, city: str) -> list[tuple]:
    """(restaurant, zone) for every catalog business whose own delivery zones include `city`.
    Internal test businesses ("Prueba ...") are never offered."""
    from .delivery import zones_of
    from .models import Restaurant
    target = find_city(city)
    if not target:
        return []
    rows = (await db.execute(select(Restaurant).where(~Restaurant.name.ilike("prueba%"))
                             .order_by(Restaurant.id))).scalars().all()
    out = []
    for r in rows:
        zone = next((z for z in zones_of(r) if find_city(z["name"]) == target), None)
        if zone:
            out.append((r, zone))
    return out


async def covers(db, restaurant, city: str) -> bool:
    return any(r.id == restaurant.id for r, _ in await covering(db, city))


def _fee(usd: float) -> str:
    return "sin costo" if not usd else "$" + f"{usd:.2f}".replace(".", ",")


async def local_options(db, city: str, phone: str = "", fees: bool = False) -> str:
    """Businesses that registered delivery to `city`, or '' when none did. The offered names are
    remembered as the current topic so "Y nacional?" right after is read in context.
    The delivery fee is shown only when asked (`fees`); otherwise it comes up while building the order."""
    hits = await covering(db, city)
    if not hits:
        return ""
    name = find_city(city).name
    if phone:
        from . import memory
        await memory.set_topic(db, phone, "recomendación de locales: " + ", ".join(r.name for r, _ in hits))
    lines = "\n".join(f"• *{r.name}*" + (f" — delivery a {z['name']} ({_fee(z['fee'])})" if fees else "")
                      for r, z in hits)
    return (f"En {name} te puedo atender con estos locales:\n"
            f"{lines}\n\n¿En cuál quieres pedir? Dime, por ejemplo, «quiero pedir en {hits[0][0].name}».")
