import pytest
from app.reactions import reaction_for

@pytest.mark.parametrize('body',['Quiero ir al cine','Cartelera en PLC','Qué películas hay?','Hola, quiero cine'])
def test_cinema_ticket_precedes_food_or_greeting(body):assert reaction_for(body)=='🎟️'

@pytest.mark.parametrize('body,emoji',[('gracias por la cartelera','🙏'),('problema con las entradas de cine','😔'),('quiero pizza','🍽️'),('estoy pensando',None)])
def test_priorities_and_no_fake_processing(body,emoji):assert reaction_for(body)==emoji

