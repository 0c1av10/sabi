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
    """Review blocker 4, updated contract (2026-11-04): pending with
    failed/stale dispatch gets re-poked (duplicate-safe: claim is atomic);
    claimed past TTL is re-driven ONCE in place (same job, no user notice);
    needs_review is never auto-resent."""
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
    assert stale_claimed.status == "pending"  # re-driven once, not errored
    assert stale_claimed.error == pilot_yummy.RETRY_MARK
    assert review.status == "needs_review"  # untouched: manual review only
    assert len(pokes) == 2  # unpoked pending job + re-driven claimed job
    notices = [e for e in sent_log if "No pude completar" in (e.get("body") or "")]
    assert len(notices) == 0  # no user notice on the first (auto-retried) failure


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


# --- Routing fix (2026-11-04): natural phrasing + route clarification ---

async def test_pedir_un_yummy_asks_route_not_food(client, Session, pokes):
    """'Quiero pedir un yummy' must enter the pilot lane (clarify route),
    not fall through to restaurant recommendations."""
    async with Session() as db:
        reply = await pilot_yummy.create_quote_job(db, PHONE, "Quiero pedir un yummy")
    assert reply and "De dónde a dónde" in reply
    assert "no se pide ningún viaje" in reply
    assert len(pokes) == 0  # nothing dispatched before the route exists
    async with Session() as db:
        rows = (await db.execute(
            pilot_yummy.select(pilot_yummy.RidesQuoteJob)
            .where(pilot_yummy.RidesQuoteJob.phone == PHONE))).scalars().all()
    assert len(rows) == 1 and rows[0].status == "awaiting_route"


async def test_taxi_context_asks_route(Session, pokes):
    """'Yummy un servicio de taxi' = ride context: clarify, never greet again."""
    async with Session() as db:
        reply = await pilot_yummy.create_quote_job(db, PHONE, "Yummy un servicio de taxi")
    assert reply and "De dónde a dónde" in reply
    assert len(pokes) == 0


async def test_followup_route_completes_job(Session, pokes):
    async with Session() as db:
        await pilot_yummy.create_quote_job(db, PHONE, "Quiero pedir un yummy")
        reply = await pilot_yummy.create_quote_job(
            db, PHONE, "de MM Plaza a Puertos de Sucre")
    assert reply and "no se pide ningún viaje" in reply
    assert len(pokes) == 1
    r_job = None
    async with Session() as db:
        r_job = (await db.execute(
            pilot_yummy.select(pilot_yummy.RidesQuoteJob)
            .where(pilot_yummy.RidesQuoteJob.phone == PHONE))).scalars().one()
    assert r_job.status == "pending"
    assert r_job.origin == "MM Plaza" and r_job.destination == "Puertos de Sucre"


async def test_followup_route_without_de(Session, pokes):
    async with Session() as db:
        await pilot_yummy.create_quote_job(db, PHONE, "Yummy un servicio de taxi")
        reply = await pilot_yummy.create_quote_job(
            db, PHONE, "MM Plaza a Puertos de Sucre")
    assert reply and "no se pide ningún viaje" in reply
    assert len(pokes) == 1


async def test_unrelated_message_dissolves_awaiting(Session, pokes):
    """A normal food message while awaiting must NOT be hijacked: the pilot
    steps aside and normal Sabi flow answers."""
    async with Session() as db:
        await pilot_yummy.create_quote_job(db, PHONE, "Quiero pedir un yummy")
        reply = await pilot_yummy.create_quote_job(db, PHONE, "quiero pizza")
    assert reply is None
    async with Session() as db:
        row = (await db.execute(
            pilot_yummy.select(pilot_yummy.RidesQuoteJob)
            .where(pilot_yummy.RidesQuoteJob.phone == PHONE))).scalars().one()
    assert row.status == "expired"
    assert await pilot_yummy.daily_job_count(db) == 0  # dissolved != consumption


async def test_cancel_while_awaiting(Session, pokes):
    async with Session() as db:
        await pilot_yummy.create_quote_job(db, PHONE, "Quiero pedir un yummy")
        reply = await pilot_yummy.create_quote_job(db, PHONE, "no, olvídalo")
    assert reply and "no cotizo nada" in reply
    assert len(pokes) == 0


async def test_awaiting_expires_after_ttl(Session, pokes):
    from datetime import timedelta
    async with Session() as db:
        await pilot_yummy.create_quote_job(db, PHONE, "Quiero pedir un yummy")
        row = (await db.execute(
            pilot_yummy.select(pilot_yummy.RidesQuoteJob)
            .where(pilot_yummy.RidesQuoteJob.phone == PHONE))).scalars().one()
        row.updated_at = pilot_yummy.utcnow() - timedelta(minutes=31)
        await db.commit()
        reply = await pilot_yummy.create_quote_job(
            db, PHONE, "de MM Plaza a Puertos de Sucre")
    assert reply is None  # window closed; route-only message is not a new intent
    assert len(pokes) == 0


async def test_non_allowlisted_pedir_yummy_untouched(Session, pokes):
    async with Session() as db:
        reply = await pilot_yummy.create_quote_job(db, "+581234567890", "Quiero pedir un yummy")
    assert reply is None
    assert len(pokes) == 0


async def test_one_shot_al_connector(Session, pokes):
    async with Session() as db:
        reply = await pilot_yummy.create_quote_job(
            db, PHONE, "cuánto cuesta el viaje de la plaza al centro")
    assert reply and "no se pide ningún viaje" in reply
    assert len(pokes) == 1


# --- Bounded auto-retry of the SAME job (2026-11-04) ---

async def test_claimed_timeout_redrives_same_job_once(client, Session, pokes):
    """Runner died mid-quote: the sweep re-drives the same row (same route,
    same recipient) exactly once, without texting the user."""
    from datetime import timedelta
    job_id = await _make_job(Session, status="claimed")
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
        job.updated_at = pilot_yummy.utcnow() - timedelta(minutes=16)
        await db.commit()
    r = await client.post("/api/pilot/yummy/jobs/claim", headers=AUTH)
    assert r.status_code == 200  # claim endpoint sweeps, then claims the re-driven job
    assert r.json()["job_id"] == str(job_id)  # SAME job, not a new request
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
    assert job.error == pilot_yummy.RETRY_MARK
    assert not [e for e in sent_log if "no pude completar" in str(e.get("body", "")).lower()]


async def test_second_timeout_notifies_user_no_third_retry(client, Session, pokes):
    from datetime import timedelta
    job_id = await _make_job(Session, status="claimed")
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
        job.error = pilot_yummy.RETRY_MARK
        job.updated_at = pilot_yummy.utcnow() - timedelta(minutes=16)
        await db.commit()
    await pilot_yummy.recover_stale_jobs(db) if False else None
    async with Session() as db:
        await pilot_yummy.recover_stale_jobs(db)
        job = await db.get(RidesQuoteJob, job_id)
    assert job.status == "error"
    assert job.error == "runner timeout after auto-retry"
    texts = [e for e in sent_log if e.get("body") and e.get("to") == PHONE]
    assert any("No pude completar" in e["body"] for e in texts)
    assert len(pokes) == 0


async def test_fresh_runner_timeout_error_is_recovered(Session, pokes):
    """If the old sweep already errored the job before the fix deployed,
    a fresh 'runner timeout' still gets its single re-drive."""
    from datetime import timedelta
    job_id = await _make_job(Session, status="pending")
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
        job.status = "error"
        job.error = "runner timeout"
        job.updated_at = pilot_yummy.utcnow() - timedelta(minutes=20)
        await db.commit()
        await pilot_yummy.recover_stale_jobs(db)
        job = await db.get(RidesQuoteJob, job_id)
    assert job.status == "pending"
    assert job.error == pilot_yummy.RETRY_MARK
    assert len(pokes) == 1


async def test_stale_runner_timeout_error_untouched(Session, pokes):
    from datetime import timedelta
    job_id = await _make_job(Session, status="pending")
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
        job.status = "error"
        job.error = "runner timeout"
        job.updated_at = pilot_yummy.utcnow() - timedelta(minutes=61)
        await db.commit()
        await pilot_yummy.recover_stale_jobs(db)
        job = await db.get(RidesQuoteJob, job_id)
    assert job.status == "error"  # too old: no blind re-drive
    assert len(pokes) == 0


# --- No-send validation mode (2026-11-04): full journey, zero WhatsApp ---

@pytest.fixture
def nosend(monkeypatch):
    monkeypatch.setattr(settings, "rides_pilot_no_send", True)
    return True


async def test_nosend_capture_validates_without_sending(client, Session, pokes, nosend):
    job_id = await _make_job(Session)
    r = await client.post("/api/pilot/yummy/jobs/claim", headers=AUTH)
    assert r.status_code == 200
    job = r.json()
    r = await client.post(f"/api/pilot/yummy/jobs/{job['job_id']}/capture",
                          content=JPEG, headers={**AUTH, "Idempotency-Key": job["job_id"]})
    assert r.status_code == 200 and r.json().get("no_send") is True
    assert not [e for e in sent_log if "image_bytes" in e]  # ZERO WhatsApp sends
    async with Session() as db:
        row = await db.get(RidesQuoteJob, int(job["job_id"]))
    assert row.status == "captured_nosend"  # terminal: phone freed, never re-driven


async def test_nosend_webhook_branch_silent(Session, pokes, nosend):
    async with Session() as db:
        reply = await pilot_yummy.create_quote_job(
            db, PHONE, "cuánto cuesta el viaje de MM Plaza a Puertos de Sucre")
    assert reply is None  # no job, no reply text: pilot quiet during validation
    assert len(pokes) == 0


async def test_nosend_second_timeout_does_not_text(Session, pokes, nosend):
    from datetime import timedelta
    job_id = await _make_job(Session, status="claimed")
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
        job.error = pilot_yummy.RETRY_MARK
        job.updated_at = pilot_yummy.utcnow() - timedelta(minutes=16)
        await db.commit()
        await pilot_yummy.recover_stale_jobs(db)
        job = await db.get(RidesQuoteJob, job_id)
    assert job.status == "error"
    assert not [e for e in sent_log if e.get("body")]  # no user notice in validation mode


# --- Manual redrive (ops endpoint, admin token) ---

ADMIN = {"Authorization": "Bearer test-admin-token"}


@pytest.fixture
def admin_token(monkeypatch):
    monkeypatch.setattr(settings, "rides_pilot_admin_token", "test-admin-token")
    return True


async def test_redrive_requires_admin_token(client, Session, pokes, admin_token):
    job_id = await _make_job(Session, status="error")
    r = await client.post("/api/pilot/yummy/jobs/redrive")
    assert r.status_code == 401
    r = await client.post("/api/pilot/yummy/jobs/redrive", headers=AUTH)  # runner token NO
    assert r.status_code == 401
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
    assert job.status == "error" and len(pokes) == 0


async def test_redrive_resets_latest_error_and_pokes(client, Session, pokes, admin_token):
    await _make_job(Session, status="done")
    job_id = await _make_job(Session, status="error")
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
        job.error = "runner timeout after auto-retry"
        await db.commit()
    r = await client.post("/api/pilot/yummy/jobs/redrive", headers=ADMIN)
    assert r.status_code == 200 and r.json()["job_id"] == str(job_id)
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
    assert job.status == "pending" and job.error == ""
    assert pokes == [job_id]  # poke fired; real poke persists dispatch_poked itself


async def test_redrive_needs_review_never_touched(client, Session, pokes, admin_token):
    job_id = await _make_job(Session, status="needs_review")
    r = await client.post("/api/pilot/yummy/jobs/redrive", headers=ADMIN)
    assert r.status_code == 204
    async with Session() as db:
        job = await db.get(RidesQuoteJob, job_id)
    assert job.status == "needs_review" and len(pokes) == 0


async def test_nosend_capture_replay_refused_no_resend(client, Session, pokes, nosend):
    job_id = await _make_job(Session)
    r = await client.post("/api/pilot/yummy/jobs/claim", headers=AUTH)
    job = r.json()
    r = await client.post(f"/api/pilot/yummy/jobs/{job['job_id']}/capture",
                          content=JPEG, headers={**AUTH, "Idempotency-Key": job["job_id"]})
    assert r.status_code == 200
    # Replay with the SAME idempotency key: refused, nothing re-sent
    r = await client.post(f"/api/pilot/yummy/jobs/{job['job_id']}/capture",
                          content=JPEG, headers={**AUTH, "Idempotency-Key": job["job_id"]})
    assert r.status_code == 409
    assert not [e for e in sent_log if "image_bytes" in e]
    # And the job is not claimable again
    r = await client.post("/api/pilot/yummy/jobs/claim", headers=AUTH)
    assert r.status_code == 204


async def test_redrive_stale_claimed_reset_fresh_claimed_untouched(client, Session, pokes, admin_token):
    from datetime import timedelta
    stale_id = await _make_job(Session, status="claimed")
    async with Session() as db:
        job = await db.get(RidesQuoteJob, stale_id)
        job.updated_at = pilot_yummy.utcnow() - timedelta(minutes=20)
        await db.commit()
    r = await client.post("/api/pilot/yummy/jobs/redrive", headers=ADMIN)
    assert r.status_code == 200 and r.json()["job_id"] == str(stale_id)
    async with Session() as db:
        job = await db.get(RidesQuoteJob, stale_id)
    assert job.status == "pending"
    assert pokes == [stale_id]

    fresh_id = await _make_job(Session, phone="p2", status="claimed")
    r = await client.post("/api/pilot/yummy/jobs/redrive", headers=ADMIN)
    assert r.status_code == 204
    async with Session() as db:
        job = await db.get(RidesQuoteJob, fresh_id)
    assert job.status == "claimed" and pokes == [stale_id]


# --- Private diagnostic shots ---

async def test_diag_upload_and_admin_retrieval(client, Session, pokes, admin_token):
    r = await client.post("/api/pilot/yummy/diag/1", content=JPEG,
                          headers={**AUTH, "X-Diag-Reason": "no prices on quote screen"})
    assert r.status_code == 200 and r.json() == {"stored": True}
    # runner token cannot read diagnostics
    r = await client.get("/api/pilot/yummy/diag/1", headers=AUTH)
    assert r.status_code == 401
    # admin token retrieves image + reason; job row untouched
    r = await client.get("/api/pilot/yummy/diag/1", headers=ADMIN)
    assert r.status_code == 200 and r.content == JPEG
    assert r.headers["x-diag-reason"] == "no prices on quote screen"


async def test_diag_requires_auth_and_valid_jpeg(client, Session, pokes):
    r = await client.post("/api/pilot/yummy/diag/1", content=JPEG)
    assert r.status_code == 401
    r = await client.post("/api/pilot/yummy/diag/1", content=b"notajpeg", headers=AUTH)
    assert r.status_code == 400
    r = await client.get("/api/pilot/yummy/diag/99", headers={"Authorization": "Bearer x"})
    assert r.status_code == 401


async def test_job_detail_admin_only(client, Session, pokes, admin_token):
    from app.models import RidesQuoteJob
    async with Session() as s:
        s.add(RidesQuoteJob(id=1, phone="+584248523168", origin="Origen X",
                            destination="Destino Y", idem_key="k1"))
        await s.commit()
    r = await client.get("/api/pilot/yummy/jobs/1", headers=AUTH)
    assert r.status_code == 401                      # runner token is not enough
    r = await client.get("/api/pilot/yummy/jobs/1", headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["origin"] == "Origen X" and body["destination"] == "Destino Y"
    r = await client.get("/api/pilot/yummy/jobs/999", headers=ADMIN)
    assert r.status_code == 404
