"""Offline: a cut-off or empty model answer to "muéstrame el menú" shows the menu, never a loop."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anthropic
import pytest

from app import service
from app.agent import grounded_retry
from app.config import settings
from app.models import MenuItem, Restaurant


def fake_model(monkeypatch, stop_reason, tool_input):
    resp = SimpleNamespace(stop_reason=stop_reason,
                           content=[SimpleNamespace(type="tool_use", input=tool_input)])

    class Client:
        def __init__(self, **_):
            self.messages = SimpleNamespace(create=AsyncMock(return_value=resp))

    monkeypatch.setattr(anthropic, "AsyncAnthropic", Client)
    monkeypatch.setattr(settings, "agent_mock_mode", False)
    monkeypatch.setattr(settings, "anthropic_api_key", "offline")
    monkeypatch.setattr(service, "refresh_rates", AsyncMock())
    monkeypatch.setattr(service, "send_whatsapp_message", AsyncMock())


async def bizza(db):
    r = Restaurant(name="Bizza", slug="bizza", owner_phone="", pin="unused")
    db.add(r)
    await db.flush()
    db.add_all([MenuItem(restaurant_id=r.id, name="TEQUEÑOS", price=9, category="Entradas"),
                MenuItem(restaurant_id=r.id, name="Pizza Margarita", price=12.5, category="Pizzas"),
                MenuItem(restaurant_id=r.id, name="Agotada", price=5, category="Pizzas", available=False)])
    await db.commit()
    return r


@pytest.mark.asyncio
async def test_cut_off_menu_answer_shows_the_menu(Session, monkeypatch):
    fake_model(monkeypatch, "max_tokens", {})
    async with Session() as db:
        r = await bizza(db)
        reply = await service.handle_inbound_message(db, r, "000-menu", "Dame el menú de BIZZA")
    assert reply.startswith("Este es el menú de Bizza:")
    assert "*Entradas*\n• TEQUEÑOS — $9,00" in reply and "• Pizza Margarita — $12,50" in reply
    assert "Agotada" not in reply and "/tienda/bizza" in reply
    assert "No te entendí" not in reply


@pytest.mark.asyncio
async def test_second_empty_answer_shows_the_menu_instead_of_repeating(Session, monkeypatch):
    fake_model(monkeypatch, "end_turn", {"reply": "", "action": "continue"})
    async with Session() as db:
        r = await bizza(db)
        first = await service.handle_inbound_message(db, r, "000-loop", "Hola")
        second = await service.handle_inbound_message(db, r, "000-loop", "Sí")
    assert first == grounded_retry(r)
    assert second.startswith("Este es el menú de Bizza:")


@pytest.mark.asyncio
async def test_cut_off_answer_without_menu_ask_keeps_the_short_retry(Session, monkeypatch):
    fake_model(monkeypatch, "max_tokens", {"reply": "Te recomiendo la pizza Marg", "action": "continue"})
    async with Session() as db:
        r = await bizza(db)
        reply = await service.handle_inbound_message(db, r, "000-cut", "Hola")
    assert reply == grounded_retry(r)
