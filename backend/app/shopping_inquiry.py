"""Bounded purchase inquiry, not product search. No current prices or external provider."""
import re
from . import memory,concierge,conversation_focus as focus

PRODUCT=re.compile(r'\b(?:laptops?|computadoras?|portatiles?|telefonos?|celulares?|tablets?|televisores?|monitores?|impresoras?)\b')
PLATFORMS={'yummy':'Yummy Marketplace','mercado libre':'Mercado Libre','mercadolibre':'Mercado Libre','facebook':'Facebook Marketplace'}

async def reply(db,phone,body):
    text=concierge._plain(body)
    explicit_platform=next((label for key,label in PLATFORMS.items() if key in text),'')
    if 'marketplace' not in text and not explicit_platform and not PRODUCT.search(text):return None
    previous=await focus.get(db,phone)
    platform=explicit_platform or (previous.platform if previous and previous.domain=='shopping' else '')
    product=previous.entity if previous and previous.domain=='shopping' else ''
    if PRODUCT.search(text):product=body.strip()[:45]
    await focus.save(db,phone,domain='shopping',entity=product,platform=platform)
    await memory.set_topic(db,phone,'compras')
    if explicit_platform:
        return (f'Entendido: {explicit_platform}.'+(f' Mantengo tu consulta de {product}.' if product else '')+
                ' La búsqueda automática de productos aún no está conectada. No tengo un precio vigente para mostrarte; necesito un modelo o un enlace como referencia.')
    if 'marketplace' in text:
        return '¿Cuál marketplace te gustaría consultar? La búsqueda automática de productos aún no está conectada en Sabi; no tengo precios vigentes sin una fuente.'
    return 'Para comparar ese producto necesito el modelo o un enlace. Aún no tengo una búsqueda de precios conectada y no puedo darte un precio vigente sin una fuente. ¿Tienes alguno que quieras comparar?'
