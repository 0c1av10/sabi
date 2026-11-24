"""/webhook/simulate speaks as any phone, so production only lets callers with the secret use it."""
from app.config import settings


async def test_simulate_open_in_local_mock_mode(client):
    r = await client.post("/webhook/simulate", json={"phone": "584140000001", "text": "hola"})
    assert r.status_code == 200 and r.json()["reply"]


async def test_simulate_locked_in_production_without_secret(client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    r = await client.post("/webhook/simulate", json={"phone": "584140000001", "text": "hola"})
    assert r.status_code == 403
    monkeypatch.delenv("VERCEL")
    monkeypatch.setattr(settings, "whatsapp_mock_mode", False)
    r = await client.post("/webhook/simulate", json={"phone": "584140000001", "text": "hola"})
    assert r.status_code == 403


async def test_simulate_needs_the_matching_secret_when_set(client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(settings, "simulate_secret", "s3cret")
    body = {"phone": "584140000001", "text": "hola"}
    assert (await client.post("/webhook/simulate", json=body)).status_code == 403
    assert (await client.post("/webhook/simulate", json=body, headers={"X-Simulate-Secret": "nope"})).status_code == 403
    r = await client.post("/webhook/simulate", json=body, headers={"X-Simulate-Secret": "s3cret"})
    assert r.status_code == 200 and r.json()["reply"]
