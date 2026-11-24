# Comercios solicitados (lista de demanda)

Decidido el 2026-11-23.

Cuando un cliente pregunta por un comercio que Sabi no tiene en el catálogo
verificado, Sabi ya responde que no lo tiene identificado y pide el enlace
oficial. Además, desde este cambio, esa solicitud queda registrada en la tabla
`requested_businesses` para que el equipo vea la demanda y vaya agregando esos
comercios.

## Qué se guarda

- `name`: el nombre del comercio tal como lo escribió el cliente.
- `name_key`: forma normalizada (minúsculas, sin acentos) para no duplicar.
- `city`: solo si el cliente la mencionó en el mensaje.
- `requests`: cuántas veces se ha pedido; cada nueva solicitud sube el contador
  en vez de crear otra fila.
- `first_requested_at` / `last_requested_at`.

Nunca se guarda el teléfono del cliente ni ningún otro dato personal.

## Reglas

- Solo se registra cuando el comercio no está en el catálogo. Si el comercio
  existe pero no cubre la ciudad pedida, no se registra (eso es cobertura, no
  un comercio faltante).
- Registrar no incorpora el comercio: agregarlo al catálogo sigue siendo una
  decisión y un proceso manual del equipo.
- La lista se consulta desde Supabase (tabla `requested_businesses`). No hay
  cambios en el panel del propietario.

## Dónde vive

- Modelo: `RequestedBusiness` en `backend/app/models.py`.
- Registro: `backend/app/requested.py` (`record`), llamado desde
  `_unresolved_place_reply` en `backend/app/routers/webhook.py`.
- La tabla se crea sola en el despliegue (`create_all` al arrancar, igual que
  las demás).
