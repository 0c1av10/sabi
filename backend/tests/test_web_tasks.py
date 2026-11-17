import pytest
from app.web_tasks import WebTask, validate_public_url, validate_action

@pytest.mark.parametrize('url',['http://yummy-marketplace.com/','https://yummy-marketplace.com.evil.test/','https://yummy-marketplace.com@evil.test/','https://127.0.0.1/','file:///etc/passwd','https://yummy-marketplace.com:444/'])
def test_bad_destinations_rejected(url):
    with pytest.raises(ValueError):validate_public_url('yummy',url)

def test_expected_destination():
    assert validate_public_url('yummy','https://yummy-marketplace.com/productos?q=gafas')

@pytest.mark.parametrize('action',['submit','buy','pay','login','click','send','execute_js','delete'])
def test_effects_not_allowed(action):
    with pytest.raises(ValueError):validate_action(action)

def test_password_not_a_fill_target():
    with pytest.raises(ValueError):validate_action('fill','password')

def test_task_state_persists_answers_and_never_claims_purchase():
    task=WebTask('mitickera','Entradas')
    task.update_facts(query='Concierto de prueba')
    assert task.missing()==['quantity']
    task.update_facts(quantity='2',password='must-not-persist')
    assert not task.missing() and 'password' not in task.facts
    with pytest.raises(ValueError):task.ready_for_review()
    with pytest.raises(ValueError):task.record('https://mitickera.com','claimed result',environment='live')
    task.record('http://127.0.0.1/','fixture only',environment='fixture')
    task.ready_for_review()
    assert 'no es carrito real' in task.summary()
    task.block('sitio no disponible')
    assert 'No pude completar' in task.summary()
