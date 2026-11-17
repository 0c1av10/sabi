"""Bounded purchase inquiry, not product search. Reuses explicit existing contact topic."""
import re
from . import memory,concierge

PRODUCT=re.compile(r'\b(?:laptops?|computadoras?|portatiles?|telefonos?|celulares?|tablets?|televisores?|monitores?|impresoras?)\b')

async def reply(db,phone,body):
    text=concierge._plain(body)
    if 'marketplace' in text:
        await memory.set_topic(db,phone,'compras:marketplace_sin_elegir')
        return '¿Cuál marketplace te gustaría consultar? La búsqueda automática de productos aún no está conectada en Sabi; puedo ayudarte a comparar enlaces que me compartas, sin inventar precios.'
    if PRODUCT.search(text):
        # Keep only explicit product words, not an invented platform, budget or preference.
        await memory.set_topic(db,phone,'compras:'+body.strip()[:65])
        return 'Para comparar ese producto necesito el modelo o un enlace. Aún no tengo una búsqueda de precios conectada y no puedo darte un precio vigente sin una fuente. ¿Tienes alguno que quieras comparar?'
    return None
