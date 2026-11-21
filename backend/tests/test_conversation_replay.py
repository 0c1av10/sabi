"""Capture real local deterministic conversations with a synthetic DB, never a live model."""
import json,os
from pathlib import Path

async def test_capture_event_journey(client,make_event,monkeypatch):
    from app.event_service import EventTools
    calls=[];original=EventTools.call
    async def capture(self,name,args):
        result=await original(self,name,args)
        calls.append({'tool':name,'arguments':args,'result':result})
        return result
    monkeypatch.setattr(EventTools,'call',capture)
    await make_event(name='Festival acústico de prueba',city='Caracas',is_demo=True)
    turns=[];sid=None
    for message in ['hola','¿Te pago a ti las entradas?','Busco un concierto en Caracas','el primero','VIP','dos entradas']:
        calls.clear()
        r=await client.post('/api/events/chat',json={'message':message,'session_id':sid})
        assert r.status_code==200
        x=r.json();sid=x['session_id'];assert x['engine']=='demo'
        turns.append({'user':message,'assistant':x['reply'],'calls':list(calls),'ui':x['ui']})
    assert '2 × VIP' in turns[-1]['assistant'] and 'no es una reserva' in turns[-1]['assistant']
    capture={'case_id':'eventos-seleccion-6turnos','evidence_mode':'deterministic_fixture',
      'synthetic_data':True,'model_calls':0,'external_reads':0,'whatsapp_sends':0,'turns':turns}
    if os.environ.get('SABI_EVAL_CAPTURE'):
        Path(os.environ['SABI_EVAL_CAPTURE']).write_text(json.dumps(capture,ensure_ascii=False,indent=2,default=str))
