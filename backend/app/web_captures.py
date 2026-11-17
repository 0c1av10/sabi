"""Step screenshots for the LOCAL fixture. No live page execution or chat sender.

A future live worker needs page-specific privacy review and safe capture regions.
This fixture gate is intentional: page text never grants capture/disclosure rights.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from urllib.parse import urlsplit


@dataclass(frozen=True)
class StepImage:
    stage: str
    source_url: str
    observed_at: str
    caption: str
    jpeg: bytes
    idempotency_key: str
    visible_delivery_verified: bool = False


async def capture_fixture_step(page, stage: str, *, environment: str) -> StepImage:
    if environment != 'fixture':
        raise ValueError('live_capture_not_enabled')
    if stage not in {'page_loaded', 'selection_updated', 'decision_needed'}:
        raise ValueError('unknown_capture_stage')
    url = page.url
    p = urlsplit(url)
    if p.scheme != 'http' or p.hostname != '127.0.0.1' or p.username or p.password:
        raise ValueError('fixture_destination_required')
    # One readable viewport, not a many-metre full-page thumbnail. The fixture
    # fits this viewport; long live articles would need reviewed, numbered crops.
    jpeg = await page.screenshot(type='jpeg', quality=85, full_page=False)
    if not jpeg.startswith(b'\xff\xd8\xff') or len(jpeg) > 3_000_000:
        raise ValueError('invalid_or_oversize_capture')
    stamp = datetime.now(timezone.utc).isoformat()
    caption = f'PRUEBA LOCAL - {stage}. Fuente: {url}. Capturada: {stamp}. Sin enviar ni pagar.'
    key = hashlib.sha256(stage.encode() + jpeg).hexdigest()
    return StepImage(stage, url, stamp, caption, jpeg, f'sabi-fixture-{key}')
