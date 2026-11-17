import pytest
from app.agent import AgentResult,guard_representation,run_agent
from app.models import Restaurant,Conversation
from app.config import settings

@pytest.mark.parametrize('text,action',[("Soy Sabi de Bizza. Te paso con el dueño",'handoff'),('Si quieres, le paso la conversación al dueño','continue'),('Puedo ayudarte','handoff')])
def test_representation_guard(text,action):
    r=guard_representation(AgentResult(reply=text,action=action),Restaurant(name='Bizza'))
    assert r.action=='continue' and 'canal humano confirmado' in r.reply and 'Sabi de Bizza' not in r.reply

async def test_hours_no_paid_model(Session,monkeypatch):
    monkeypatch.setattr(settings,'anthropic_api_key','synthetic-not-a-key')
    monkeypatch.setattr(settings,'agent_mock_mode',False)
    from app import agent
    async def forbidden(*a,**k):raise AssertionError('no model call allowed')
    monkeypatch.setattr(agent,'run_llm_agent',forbidden)
    async with Session() as db:
        r=Restaurant(id=999,name='Bizza',opening_hours='')
        c=Conversation(state_json='{}')
        result=await run_agent(db,r,c,[],'De bizza cuál es el horario')
        assert 'No tengo un horario verificado de Bizza' in result.reply
        assert result.action=='continue'
        r.opening_hours='12:00–22:00'
        assert 'registrado' in (await run_agent(db,r,c,[],'horario')).reply
