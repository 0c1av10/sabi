"""DB-unique claim shared by all processes, before replies, reactions or jobs."""
import hashlib
import logging
from sqlalchemy.exc import IntegrityError
from .models import InboundReceipt

logger=logging.getLogger(__name__)


async def claim_inbound(db,provider,phone,message_id,*,platform_id=''):
    # Platform WhatsApp IDs dedupe the same message across integration routes.
    # Provider IDs are namespaced when no platform ID was supplied. Never text/time.
    identity=platform_id or message_id
    if not phone or not isinstance(identity,str) or not identity or len(identity)>512:
        logger.warning('inbound_without_stable_identity provider=%s',provider)
        return False
    scope='whatsapp' if platform_id or identity.startswith('wamid.') else provider
    key=hashlib.sha256((scope+'\0'+phone+'\0'+identity).encode()).hexdigest()
    db.add(InboundReceipt(key=key,provider=provider))
    try:await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.info('inbound_duplicate_suppressed provider=%s receipt=%s',provider,key[:12])
        return False
    logger.info('inbound_dispatch_claimed provider=%s receipt=%s',provider,key[:12])
    return True
