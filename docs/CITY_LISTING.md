# Listado por ciudad: cobertura no confirmada se aclara, no se oculta

Decidido el 2026-11-23 (Octavio: "Incluye todos").

Cuando un cliente pide comida en una ciudad, Sabi lista los locales del catálogo
visible de esta forma:

1. **Con delivery registrado a esa ciudad**: aparecen primero, con la zona y el
   costo solo si el cliente pregunta por tarifas.
2. **Sin zonas registradas en absoluto** (dato desconocido): aparecen también,
   marcados como "sin delivery a esa ciudad confirmado todavía"; el local
   confirma cobertura y costo al aprobar el pedido. Dato desconocido nunca se
   lee como inexistente.
3. **Con zonas registradas en otras ciudades**: no aparecen para esta ciudad;
   sus propios datos dicen dónde entregan. Tampoco se prometen.

Las reglas de pedido no cambian: ningún negocio promete entrega en una ciudad
que sus datos no registran (`covers` sigue respondiendo solo con zonas
registradas). Los comercios ocultos (demo/prueba) nunca aparecen, ni siquiera
en la sección de cobertura por confirmar.

## Reconocimiento al mencionar

Mencionar un comercio visible sin zonas registradas NO lo vuelve "lugar no
identificado": Sabi lo reconoce y lo enruta normalmente; la cobertura y el
costo los confirma el local al aprobar el pedido. Pedir su enlace oficial de
nuevo leería como no conocerlo (evidencia real: "Bizza también queda en
lechería", 2026-11-23). Si el cliente escribe una ciudad nueva para ese
comercio, la ciudad anterior de la conversación nunca se le impone: la tarea
queda sin ciudad hasta que el local confirme.

## Dónde vive

- `local_options` en `backend/app/venezuela.py` arma el listado; `covering` y
  `covers` no cambian.
- `_unresolved_place_reply` en `backend/app/routers/webhook.py` reconoce los
  comercios visibles sin zonas; la herencia de ciudad en `_resolve` exige que
  el mensaje no haya nombrado otra ciudad.
- Pruebas: `backend/tests/test_city_listing.py`.
