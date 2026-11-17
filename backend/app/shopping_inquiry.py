"""Shopping inquiry with explicit Yummy public-source search. No purchases."""
import re
from . import memory,concierge,conversation_focus as focus,product_search

PRODUCT=re.compile(r'\b(?:laptops?|computadoras?|portatiles?|telefonos?|celulares?|tablets?|televisores?|monitores?|impresoras?|audifonos?|licuadoras?|neveras?|lavadoras?|zapatos?|perfumes?|relojes?|sillas?)\b')
PLATFORMS={'yummy':'Yummy Marketplace','mercado libre':'Mercado Libre','mercadolibre':'Mercado Libre','facebook':'Facebook Marketplace'}

async def reply(db,phone,body):
    text=concierge._plain(body)
    if re.search(r'\b(taxi|rides?|viaje|carrera|moto|transporte)\b',text) and 'marketplace' not in text:return None
    explicit_platform=next((label for key,label in PLATFORMS.items() if key in text),'')
    if 'marketplace' not in text and not explicit_platform and not PRODUCT.search(text):return None
    previous=await focus.get(db,phone)
    platform=explicit_platform or (previous.platform if previous and previous.domain=='shopping' else '')
    product=previous.entity if previous and previous.domain=='shopping' else ''
    if PRODUCT.search(text):product=body.strip()[:100]
    elif explicit_platform and re.search(r'\b(busca|buscame|necesito|quiero|compara)\b',text):
        candidate=product_search.query_for(body)
        if candidate:product=candidate
    active=await focus.save(db,phone,domain='shopping',entity=product,platform=platform)
    version=active.updated_at
    await memory.set_topic(db,phone,'compras')
    if platform=='Yummy Marketplace':
        query=product_search.query_for(product)
        if not query:return '¿Qué producto buscas en Yummy Marketplace?'
        result=await product_search.search_yummy(query)
        current=await focus.get(db,phone)
        if not current or current.domain!='shopping' or current.updated_at!=version:return ''
        return product_search.format_result(result,query)
    if explicit_platform:
        return (f'Entendido: {explicit_platform}.'+(f' Mantengo tu consulta de {product}.' if product else '')+
                ' La búsqueda automática de productos aún no está conectada. No tengo un precio vigente para mostrarte; necesito un modelo o un enlace como referencia.')
    if 'marketplace' in text:
        return '¿Cuál marketplace te gustaría consultar? Puedo buscar publicaciones de Yummy Marketplace; otros sitios todavía necesitan una fuente verificada.'
    return '¿Te gustaría que lo busque en Yummy Marketplace? Para comparar un equipo concreto también puedes pasarme el modelo o un enlace.'
