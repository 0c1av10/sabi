import pytest
from app.web_captures import capture_fixture_step

class Page:
    url='http://127.0.0.1:1234/'
    calls=0
    async def screenshot(self,**kw):
        self.calls+=1
        assert kw=={'type':'jpeg','quality':85,'full_page':False}
        return b'\xff\xd8\xfffixture-jpeg-contract-only'

@pytest.mark.asyncio
async def test_fixture_capture_has_provenance_but_never_claims_delivery():
    page=Page()
    result=await capture_fixture_step(page,'decision_needed',environment='fixture')
    assert result.source_url==page.url and result.observed_at
    assert 'PRUEBA LOCAL' in result.caption and not result.visible_delivery_verified
    assert result.idempotency_key.startswith('sabi-fixture-')

@pytest.mark.asyncio
async def test_live_capture_and_unknown_stage_stay_disabled():
    page=Page()
    for stage,env in [('decision_needed','live'),('password','fixture')]:
        with pytest.raises(ValueError):await capture_fixture_step(page,stage,environment=env)
    page.url='https://www.mitickera.com/'
    with pytest.raises(ValueError):await capture_fixture_step(page,'decision_needed',environment='fixture')
    assert page.calls==0
