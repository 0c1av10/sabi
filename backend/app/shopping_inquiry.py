"""Bounded purchase inquiry, not product search. No current prices or external provider."""
import re
from . import memory,concierge

PRODUCT=re.compile(r'\b(?:laptops?|computadoras?|portatiles?|telefonos?|celulares?|tablets?|televisores?|monitores?|impresoras?)\b')
PLATFORMS={'yummy':'Yummy Marketplace','mercado libre':'Mercado Libre','mercadolibre':'Mercado Libre','facebook':'Facebook Marketplace'}

async def reply(db,phone,body):
    text=concierge._plain(body)
    explicit_platform=next((label for key,label in PLATFORMS.items() if key in text),'')
    contact=await memory.get(db,phone)
    previous=(contact.last_topic or '') if contact else ''
    platform=explicit_platform
    product=''
    if previous.startswith('compras:'):
        bits=previous[len('compras:'):].split('|',1)
        platform=platform or bits[0]
        product=bits[1] if len(bits)>1 else ''
    if PRODUCT.search(text):product=body.strip()[:45]
    if 'marketplace' not in text and not explicit_platform and not PRODUCT.search(text):return None
    await memory.set_topic(db,phone,'compras:'+platform+'|'+product)
    if explicit_platform:
        return (f'Entendido: {explicit_platform}.'+(f' Mantengo tu consulta de {product}.' if product else '')+
                ' La búsqueda automática de productos aún no está conectada. No tengo un precio vigente para mostrarte; necesito un modelo o un enlace como referencia.')
    if 'marketplace' in text:
        return '¿Cuál marketplace te gustaría consultar? La búsqueda automática de productos aún no está conectada en Sabi; no tengo precios vigentes sin una fuente.'
    return 'Para comparar ese producto necesito el modelo o un enlace. Aún no tengo una búsqueda de precios conectada y no puedo darte un precio vigente sin una fuente. ¿Tienes alguno que quieras comparar?'
