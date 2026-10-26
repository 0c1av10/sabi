import pytest

from app import gym_whatsapp as g


def test_intent_matches_boxing_requests():
    for text in ("quiero reservar una clase de boxeo", "hola, Domicio Rondón Boxing Gym", "busco un gym para entrenar"):
        assert g.GYM_INTENT.search(g._plain(text)), text
    assert not g.GYM_INTENT.search(g._plain("quiero unos pastelitos"))


def test_level_parsing():
    assert g._level("nunca he boxeado") == "principiante"
    assert g._level("soy avanzado") == "avanzado"
    assert g._level("no sé") == ""


def test_memory_extracts_names_without_false_positives():
    from app import memory as m
    assert m.extract_name("me llamo octavio caamaño") == "Octavio Caamaño"
    assert m.extract_name("hola soy Maria y quiero una clase") == "Maria"
    assert m.extract_name("soy principiante") == ""
    assert m.extract_name("quiero unos pastelitos") == ""
    assert m.clean_name("🔥🔥") == ""
    assert m.FORGET.search("olvídame por favor")
