"""Reviewed public directory, separate from merchant tenants. No autonomous web search."""
from datetime import datetime,timezone
from .concierge import _plain
RECORDS=[{
    'name':"Abruzzo's Pizzería",'aliases':['abruzzos',"abruzzo's",'abruzzo'],
    'city':'Lechería','address':'Av. Principal de Lechería, referencia KIA Motors',
    'source':'https://www.threads.com/@abruzzospizzeria',
    'corroboration':'https://asgastronomico.com/abruzzos-pizzeria/',
    'observed_at':'2026-11-17T07:39:24+00:00','expires_at':'2026-11-18T07:39:24+00:00',
    'evidence':'La ricetta della nonna; Lecheria (Av. Principal, KIA Motors)',
    'menu_verified':False,'orders_supported':False}]

def lookup(name,city,now=None):
    now=now or datetime.now(timezone.utc)
    matches=[r for r in RECORDS if _plain(name) in [_plain(x) for x in r['aliases']] and _plain(city)==_plain(r['city'])]
    if len(matches)!=1:return f'No tengo una fuente revisada vigente para {name} en {city}. La búsqueda web automática aún no está conectada; no voy a sustituirlo por otro local.'
    r=matches[0]
    if datetime.fromisoformat(r['expires_at'])<=now:return f'La información guardada de {r["name"]} necesita una consulta nueva. No tengo una búsqueda web automática conectada para actualizarla ahora.'
    return (f'La ficha revisada corresponde a {r["name"]}, en {r["address"]}. Su perfil publica esa sede en {r["city"]}.\n'
            f'Fuente revisada el 17/11/2026: {r["source"]}\nNo tengo menú ni disponibilidad de pedidos verificados para esa sede. No es un comercio incorporado a Sabi.')
