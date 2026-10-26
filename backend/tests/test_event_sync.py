from app import event_sync as s

DETAIL = {
    "slug": "beele", "title": "Beele - Caracas", "tour_name": "Detone", "status": "PUBLISHED",
    "currency": "EUR", "starts_at": "2026-11-06T21:00:00.000000Z", "image": "storage/x.webp",
    "short_description": "<p>Hola</p>", "venta": {"abierta": True}, "online_sales_enabled": True,
    "venue": {"name": "Parque Bolivar", "city": {"name": "Caracas"}},
    "ticket_types": [{"name": "VIP", "price": 163, "available": 10},
                     {"name": "BOX", "price": 550, "available": 0},
                     {"name": "FREE", "price": 0, "available": 5}],
}


def test_parse_event_zones_and_link():
    it = s.parse_event(DETAIL)
    assert it["city"] == "Caracas" and it["status"] == "publicado"
    assert it["purchase_url"].endswith("/eventos/beele/entradas")
    assert [(z["name"], z["price_minor"], z["availability"]) for z in it["zones"]] == [
        ("VIP", 16300, "disponible"), ("BOX", 55000, "agotado")]


def test_closed_sales_do_not_claim_availability():
    it = s.parse_event({**DETAIL, "venta": {"abierta": False}})
    assert {z["availability"] for z in it["zones"]} == {"por_confirmar"}


def test_parse_event_rejects_incomplete():
    assert s.parse_event({**DETAIL, "venue": {}}) is None
    assert s.parse_event({**DETAIL, "currency": "XXX"}) is None


def test_collect_slugs_includes_tour_events():
    payload = {"data": [{"type": "event", "slug": "a"},
                        {"type": "tour", "countries": [{"cities": [{"events": [{"slug": "b"}]}]}]}]}
    assert s.collect_slugs(payload) == ["a", "b"]


def test_product_stemming_matches_plural_to_menu_word():
    from app.auth import _norm, _same, _stem
    asked = {_stem(w) for w in _norm("quiero unos pastelitos") if len(w) >= 4}
    menu = {_stem(w) for w in _norm("Pastelito de Queso")}
    assert any(_same(a, m) for a in asked for m in menu)
