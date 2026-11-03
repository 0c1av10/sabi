"""Yummy Rides quote pilot (pull model): contract tests over the ASGI app.

Offline: per-test SQLite, WhatsApp mock mode (sent_log is the provider
stand-in), dispatch poke stubbed. No external calls, no spend.
Covers the contract agreed for backend -> dispatch -> claim -> JPEG ->
WhatsApp delivery, including its declared AT-LEAST-ONCE limit.
"""
import asyncio

import pytest

from app import pilot_yummy
from app.config import settings
from app.models import RidesQuoteJob
from app.whatsapp import sent_log

AUTH = {"Authorization": "Bearer test-runner-token"}
JPEG = b"\xff\xd8\xff" + b"\xe0" + b"\x00" * 100 + b"\xff\xd9"
PHONE = "+584248523168"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    # Patch the settings singleton: safe under any test-import order (the
    # shared Settings object is created before this module is imported).
    monkeypatch.setattr(settings, "rides_pilot_allowed_phones",
                        "+584248523168,p2,p3,p4,p5,p6,p7,p8,p9,p10,p11,p12")
    monkeypatch.setattr(settings, "rides_pilot_runner_token", "test-runner-token")
    monkeypatch.setattr(settings, "gh_dispatch_token", "")
    sent_log.clear()
    yield
    sent_log.clear()


@pytest.fixture
def pokes(monkeypatch):
    """Stub the GitHub dispatch poke; records calls without any network."""
    calls = []

    async def fake(db, job):
        calls.append(job.id)
        job.dispatch_poked = True   # mirror the real poke's persisted flag
        return True

    monkeypatch.setattr(pilot_yummy, "dispatch_poke", fake)
    return calls


async def _make_job(Session, phone=PHONE, origin="MM Plaza", dest="Puertos de Sucre",
                    status="pending"):
    async with Session() as db:
        job = RidesQuoteJob(phone=phone, origin=origin, destination=dest, status=status)
        db.add(job)
        await db.commit()
        return job.id


async def test_happy_path(client, Session, pokes):
    async with Session() as db:
        reply = await pilot_yummy.create_quote_job(
            db, PHONE, "cuánto cuesta el viaje de MM Plaza a Puertos de Sucre")
    assert reply and "no se pide ningún viaje" in reply
    assert len(pokes) == 1
    r = await client.post("/api/pilot/yummy/jobs/claim", headers=AUTH)
    assert r.status_code == 200
    job = r.json()
    assert job["origin"] == "MM Plaza" and job["dest"] == "Puertos de Sucre"
    r = await client.post(f"/api/pilot/yummy/jobs/{job['job_id']}/capture",
                          content=JPEG, headers={**AUTH, "Idempotency-Key": job["job_id"]})
    assert r.status_code == 200
    images = [e for e in sent_log if "image_bytes" in e]
    assert len(images) == 1
    assert images[0]["to"] == PHONE  # recipient from the job record, never the runner


async def test_concurrent_double_claim(client, Session, pokes):
    await _make_job(Session)
    results = await asyncio.gather(*[
        client.post("/api/pilot/yummy/jobs/claim", headers=AUTH) for _ in range(8)])
    codes = sorted(r.status_code for r in results)
    assert codes.count(200) == 1 and codes.count(204) == 7


async def test_replay_after_done_dedupes(client, Session, pokes):
    jid = await _make_job(Session, status="claimed")
    for _ in range(3):
        r = await client.post(f"/api/pilot/yummy/jobs/{jid}/capture", content=JPEG,
                              headers={**AUTH, "Idempotency-Key": str(jid)})
        assert r.status_code == 200
    assert len([e for e in sent_log if "image_bytes" in e]) == 1


async def test_ambiguous_send_needs_review_no_blind_resend(client, Session, monkeypatch):
    async def failing_send(*a, **k):
        return {"error": "timeout after request left"}

    monkeypatch.setattr(pilot_yummy, "send_whatsapp_image", failing_send)
    jid = await _make_job(Session, status="claimed")
    r = await client.post(f"/api/pilot/yummy/jobs/{jid}/capture", content=JPEG,
                          headers={**AUTH, "Idempotency-Key": str(jid)})
    assert r.status_code == 202 and r.json()["status"] == "needs_review"
    r = await client.post(f"/api/pilot/yummy/jobs/{jid}/capture", content=JPEG,
                          headers={**AUTH, "Idempotency-Key": str(jid)})
    assert r.status_code == 202  # replay: still no resend


async def test_invalid_jpeg_rejected_by_content(client, Session):
    jid = await _make_job(Session, status="claimed")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    r = await client.post(f"/api/pilot/yummy/jobs/{jid}/capture", content=png,
                          headers={**AUTH, "Content-Type": "image/jpeg",
                                   "Idempotency-Key": str(jid)})
    assert r.status_code == 400 and r.json()["error"] == "invalid_jpeg"
    big = b"\xff\xd8\xff" + b"\x00" * (settings.rides_pilot_max_jpeg_bytes + 1)
    r = await client.post(f"/api/pilot/yummy/jobs/{jid}/capture", content=big,
                          headers={**AUTH, "Idempotency-Key": str(jid)})
    assert r.status_code == 400
    assert not [e for e in sent_log if "image_bytes" in e]


async def test_foreign_job_bad_token_and_allowlist(client, Session, pokes):
    r = await client.post("/api/pilot/yummy/jobs/99999/capture", content=JPEG,
                          headers={**AUTH, "Idempotency-Key": "x"})
    assert r.status_code == 404
    r = await client.post("/api/pilot/yummy/jobs/claim",
                          headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    async with Session() as db:
        reply = await pilot_yummy.create_quote_job(
            db, "+580000000000", "cuánto cuesta el viaje de A a B")
    assert reply is None and not pokes


async def test_daily_consumption_cap(Session, monkeypatch, pokes):
    monkeypatch.setattr(settings, "rides_pilot_daily_max", 3)
    async with Session() as db:
        assert await pilot_yummy.create_quote_job(db, "p2", "precio del viaje de A a B")
        assert await pilot_yummy.create_quote_job(db, "p3", "precio del viaje de A a B")
        assert await pilot_yummy.create_quote_job(db, "p4", "precio del viaje de A a B")
        capped = await pilot_yummy.create_quote_job(db, "p5", "precio del viaje de A a B")
        assert "límite" in capped
    assert len(pokes) == 3  # cap reached: no fourth dispatch


async def test_second_request_same_phone_is_busy_no_new_job(client, Session, pokes):
    async with Session() as db:
        first = await pilot_yummy.create_quote_job(db, PHONE, "tarifa del viaje de A a B")
        second = await pilot_yummy.create_quote_job(db, PHONE, "tarifa del viaje de C a D")
    assert first and "en curso" in second
    assert len(pokes) == 1  # one job, one poke


async def test_dispatch_without_token_stays_pending(Session):
    async with Session() as db:
        job = RidesQuoteJob(phone=PHONE, origin="A", destination="B")
        db.add(job)
        await db.commit()
        assert await pilot_yummy.dispatch_poke(db, job) is False
        assert job.dispatch_poked is False  # retriable later; nothing sent anywhere


# --- Blocker fixes from independent review (2026-11-03) ---

async def test_quote_reaches_pilot_without_restaurant(client, Session, pokes):
    """Personal WhatsApp ask, no business context: the hook fires before
    restaurant routing (review blocker 1)."""
    payload = {"entry": [{"changes": [{"value": {
        "messages": [{"type": "text", "from": "584248523168",
                      "id": "wamid.test", "text": {"body":
                          "cuánto cuesta el viaje de MM Plaza a Puertos de Sucre"}}],
        "contacts": []}}]}]}
    r = await client.post("/webhook/whatsapp", json=payload)
    assert r.status_code == 200
    assert len(pokes) == 1
    texts = [e for e in sent_log if e.get("body")]
    assert any("no se pide ningún viaje" in e["body"] for e in texts)
    assert texts[-1]["to"] == "584248523168"


async def test_recovery_repokes_and_expires_claimed(client, Session, pokes):
    """Review blocker 4: pending with failed/stale dispatch gets re-poked
    (duplicate-safe: claim is atomic); claimed past TTL errors out and frees
    the phone with a one-time notice; needs_review is never auto-resent."""
    from datetime import timedelta
    from app.models import utcnow
    async with Session() as db:
        stale_claimed = RidesQuoteJob(phone=PHONE, origin="A", destination="B",
                                      status="claimed")
        db.add(stale_claimed)
        pending = RidesQuoteJob(phone="p7", origin="C", destination="D",
                                status="pending", dispatch_poked=False)
        db.add(pending)
        review = RidesQuoteJob(phone="p8", origin="E", destination="F",
                               status="needs_review")
        db.add(review)
        await db.commit()
        from sqlalchemy import update
        await db.execute(update(RidesQuoteJob)
                         .where(RidesQuoteJob.id == stale_claimed.id)
                         .values(updated_at=utcnow() - timedelta(minutes=20)))
        await db.commit()
        await pilot_yummy.recover_stale_jobs(db)
        await db.refresh(stale_claimed)
        await db.refresh(review)
    assert stale_claimed.status == "error"
    assert review.status == "needs_review"  # untouched: manual review only
    assert pokes  # the unpoked pending job got poked
    notices = [e for e in sent_log if "No pude completar" in (e.get("body") or "")]
    assert len(notices) == 1 and notices[0]["to"] == PHONE


async def test_zernio_conversation_fallback_off_cache(Session):
    """Review blocker 5: serverless instances lose the in-memory conversation
    cache; the resolver must fall back to the Zernio API."""
    from app.whatsapp import _zernio_conversation_id, zernio_conversations
    zernio_conversations.clear()

    class _Resp:
        status_code = 200
        def json(self):
            return {"data": [{"id": "conv-9", "participantId": "584248523168"}]}

    class _Client:
        async def get(self, *a, **k):
            return _Resp()

    conv = await _zernio_conversation_id(_Client(), "+584248523168")
    assert conv == "conv-9"
    assert zernio_conversations["584248523168"] == "conv-9"  # re-cached


async def test_phone_allowlist_digit_normalized(Session):
    """Providers deliver phone in different shapes; allowlist matches on digits."""
    assert pilot_yummy.pilot_allowed("+584248523168")
    assert pilot_yummy.pilot_allowed("584248523168")
    assert not pilot_yummy.pilot_allowed("+589999999999")
