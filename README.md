## Pagos y aprobación

Los pedidos pueden indicar pago móvil, Zelle, transferencia o efectivo. Sabi registra el método y la referencia; el comercio confirma manualmente que recibió el pago en el panel y luego pulsa **Aprobar**. Solo después de esas dos acciones se envía la confirmación automática al cliente. El MVP no cobra tarjetas ni verifica transferencias por API.

# Sabi (MVP)

Agente de ventas por WhatsApp con IA para restaurantes. Atiende 24 horas, toma
pedidos de forma estructurada y el dueño aprueba cada pedido antes de que se
confirme al cliente.

## Arquitectura

- `backend/` — FastAPI (Python 3.12): webhook de WhatsApp Cloud API, agente
  Claude con salida JSON estructurada, bandeja de aprobación, registro.
- `web/` — Panel Next.js + Tailwind: login por restaurante, CRUD de menú,
  bandeja de aprobación, registro del día, configuración.
- Base de datos — SQLAlchemy async. SQLite en local; Postgres/Supabase vía
  `DATABASE_URL` sin cambiar código.

## Variables de entorno

Copiá `.env.example` a `backend/.env`:

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./sabi.db` local, o la URI de Supabase (Connect → Session pooler, `postgresql://postgres.<ref>:<password>@...pooler.supabase.com:5432/postgres`; se convierte sola a asyncpg) |
| `ANTHROPIC_API_KEY` | API key de Anthropic |
| `ANTHROPIC_MODEL` | Modelo Claude (default: claude-sonnet-5-5) |
| `AGENT_MOCK_MODE` | `true` = agente determinista sin LLM (pruebas sin key) |
| `WHATSAPP_TOKEN` | Token permanente de WhatsApp Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | phone_number_id del número de Meta |
| `WHATSAPP_VERIFY_TOKEN` | Token de verificación del webhook (elegilo vos) |
| `WHATSAPP_MOCK_MODE` | `true` = mensajes salientes solo se loguean |
| `WHATSAPP_PROVIDER` | `zernio`, `kapso` o `meta`; vacío = el primero que tenga key |
| `ZERNIO_API_KEY` / `ZERNIO_ACCOUNT_ID` / `ZERNIO_WEBHOOK_SECRET` | Envío por el inbox de Zernio y webhook firmado `POST /webhook/zernio` (`message.received`, `X-Zernio-Signature`) |
| `KAPSO_API_KEY` / `KAPSO_PHONE_NUMBER_ID` | Envío por Kapso (`api.kapso.ai/meta/whatsapp`); tiene prioridad sobre `WHATSAPP_TOKEN` |
| `KAPSO_WEBHOOK_SECRET` | Secreto HMAC del webhook de Kapso (`POST /webhook/kapso`, evento `whatsapp.message.received`) |
| `SESSION_SECRET` | Secreto para firmar sesiones del panel |

## Correr en local

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed          # crea "NACIONAL Restaurante" (slug: nacional, PIN: 1234)
uvicorn app.main:app --reload   # http://localhost:8000
```

```bash
cd web
npm install
npm run dev                     # http://localhost:3000 (proxy a :8000)
```

Login del panel: slug `nacional`, PIN `1234`.

## Guion de prueba (sin credenciales reales)

Con `AGENT_MOCK_MODE=true` y `WHATSAPP_MOCK_MODE=true`:

```bash
cd backend && python -m scripts.simulate_e2e
```

Simula: cliente saluda → pide pollo entero a la brasa + 2 papelones → delivery → dirección →
confirma → pedido queda pendiente → dueño aprueba por API → confirmación al
cliente queda registrada en el log de WhatsApp y en la conversación.

El endpoint `POST /webhook/simulate` (`{"phone","text","name"}`) corre el mismo
pipeline que el webhook real, para probar conversaciones desde curl o el panel.

## WhatsApp Cloud API (producción)

1. Crear app en Meta for Developers → producto WhatsApp → número de prueba.
2. `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`.
3. `WHATSAPP_MOCK_MODE=false`, `AGENT_MOCK_MODE=false`, `ANTHROPIC_API_KEY`.
4. Exponer el backend (ngrok/Railway/Render) y configurar el webhook:
   `GET/POST https://<host>/webhook/whatsapp` con el verify token.

## Flujo del pedido

1. Cliente escribe → webhook → agente (Claude, JSON estricto: `reply`, `action`,
   `order`). El agente solo usa ítems del menú; si no sabe, ofrece pasar al dueño.
2. Pedido completo → el agente repite el resumen al cliente.
3. Cliente valida → `orders` con `status=pending` → aviso al dueño por WhatsApp.
4. Dueño aprueba/edita/rechaza en el panel → solo ahí el cliente recibe la
   confirmación (o el rechazo con motivo) por WhatsApp.

## Modelo de datos

`restaurants`, `menu_items`, `customers`, `conversations`, `messages`,
`orders` (pending|approved|rejected|edited), `order_items`.

## Fuera de alcance (v0.1)

POS, pagos, multi-sucursal, reservas, analítica avanzada.

## Multimoneda (USD / EUR / Bs)

Los precios del menú se cargan en dólares. El dueño fija las tasas del día (Bs por 1 USD y Bs por 1 EUR, como las publica el BCV) en **Configuración**; el agente, la bandeja y el menú muestran cada monto en las tres monedas (`$10,20 · €9,40 · Bs 372,30`).

## Tienda online por local

- **Alta:** el formulario "Crea tu tienda" de la landing llama a `POST /api/onboarding` (nombre, correo, WhatsApp y web opcional). Crea el restaurante con su slug y un PIN de 4 dígitos que se muestra en pantalla (todavía no se envía por correo).
- **Lectura de la web** (`backend/app/importer.py`, sin IA): nombre, frase, logo, color (`theme-color`) y platos con precio desde JSON-LD, objetos de menú en el HTML o en los JS del mismo dominio, y líneas de texto con precio. Solo URLs públicas (bloquea IPs privadas). Si no encuentra la carta, arranca con un menú base editable.
- **Tienda pública:** `/tienda/<slug>` (`GET /api/store/<slug>`), con carrito, delivery o retiro y precios en $, € y Bs.
- **Checkout:** `POST /api/store/<slug>/orders` valida los platos contra el menú y crea el pedido `pending` con `source="tienda"`. Llega a la misma bandeja y se confirma al cliente por WhatsApp solo cuando el dueño lo aprueba.
- **Panel → Tienda:** link para compartir, releer la carta desde la web (`POST /api/store/import`, agrega platos y actualiza precios sin borrar) y editar logo, color, frase y correo.

## Supabase (Postgres)

Con `DATABASE_URL` apuntando a Supabase, el backend crea las tablas al arrancar, usa `NullPool` y desactiva el caché de prepared statements de asyncpg (compatible con el pooler en modo session o transaction) y activa RLS en todas las tablas de `public`. Sin políticas, los roles `anon`/`authenticated` de la Data API no ven nada; el backend se conecta como dueño de las tablas. Con `DEMO_AUTOSEED=true` solo se crea "NACIONAL Restaurante" si no existe: los datos ya no se borran.

## Asistente de eventos (demo FC Producciones)

Demostración **independiente** para presentar la propuesta: Sabi conversa, recomienda eventos de un catálogo local, muestra zonas y precios de referencia, calcula un subtotal orientativo y entrega el **enlace oficial** de TuEntradaWeb. **No** es una integración oficial ni una alianza aprobada, y Sabi **no compra por el usuario**: el pago ocurre en la plataforma externa.

- Chat: `/eventos` (mobile-first, con distintivo "Demo").
- Panel: `/eventos/admin` (catálogo, conversaciones, clics, pagos reportados, métricas, CSV).
- API: `backend/app/routers/events.py` (público) y `events_admin.py` (admin).

### Reglas del flujo

| Estado | Qué significa | Quién lo produce |
|---|---|---|
| Interés registrado | El usuario preguntó por un evento/zona | Sabi (herramienta) |
| Selección preparada | Zona + cantidad + subtotal orientativo. **No es reserva** | Backend |
| Clic en enlace | Se abrió el enlace oficial. **No implica checkout ni compra** | Ruta `/api/events/go/{id}` |
| Pago reportado | El usuario dijo "ya pagué". **No confirma nada** | Sabi (herramienta) |
| Compra confirmada | Verificación humana con referencia, importe, moneda, nota, admin y fecha | **Solo un admin autenticado** |

Atribución: se muestra como *manual* y solo existe si hay una compra confirmada vinculada a la conversación. Sin confirmaciones, los ingresos muestran "Sin datos".

### Correr en local (sin credenciales externas)

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
EVENTS_ADMIN_EMAILS=tu@correo.com EVENTS_ADMIN_PASSWORD=una-clave-larga uvicorn app.main:app --reload
# otra terminal
cd web && npm install && npm run dev     # http://localhost:3000/eventos
```

Sin `ANTHROPIC_API_KEY`, o con `EVENTS_AGENT_MODE=demo` (o `AGENT_MOCK_MODE=true` en modo `auto`), el agente usa el **motor de demostración determinista**, con el mismo contrato de herramientas que el motor real y sin llamadas externas. Con la key, usa Claude con *tool calling* (máx. `EVENTS_MAX_TOOL_CALLS` por turno, timeout `EVENTS_AGENT_TIMEOUT_SECONDS`) y, si falla, cae al motor de demostración.

Con `EVENTS_DEMO_SEED=true` se crean tres eventos ficticios (Caracas, Valencia, Maracaibo) solo si el catálogo está vacío. Tienen `is_demo=true`: **la compra externa está desactivada** ("Configura un enlace oficial para habilitar la compra"). Uno de ellos tiene datos sin verificar a propósito, para ver los avisos. Con SQLite local los datos viven en `backend/sabi.db`; en Vercel sin `DATABASE_URL` de Postgres no hay persistencia real entre despliegues.

### Habilitar la compra con un enlace oficial

1. Entra a `/eventos/admin` con un correo de `EVENTS_ADMIN_EMAILS` y la clave `EVENTS_ADMIN_PASSWORD`.
2. Crea un evento (o edita uno) **sin** marcar "datos de demostración", estado `publicado`, y pega el enlace https que TuEntradaWeb te haya confirmado. Sabi no construye URLs de checkout ni parámetros de selección.
3. Agrega zonas con precio de referencia y marca "acabo de verificar" cuando lo hayas comprobado en la plataforma.
4. El botón del chat apunta a `/api/events/go/{evento}`, que resuelve el destino **desde el catálogo** (nunca desde la petición), registra el clic y redirige. Si defines `EVENTS_ALLOWED_PURCHASE_HOSTS`, solo se aceptan esos dominios.

### Seguridad (resumen)

- Cada herramienta valida con Pydantic estricto (`extra=forbid`, enteros estrictos) y se autoriza en el servidor; `conversation_id` lo inyecta el servidor, el modelo no lo controla. Precios y subtotales salen de la base de datos en **centavos enteros**; no se suman ni convierten monedas.
- Textos de eventos y mensajes se tratan como datos; el *system prompt* no cambia por pedido del usuario; se corrigen respuestas que afirmen reserva/pago.
- Límite de mensajes por conversación y global, límite de intentos de login (persistido en BD), cookie `HttpOnly`/`SameSite=Lax`/`Secure`, CSV con neutralización de fórmulas.
- Supabase: RLS activo con política de denegación para `anon`/`authenticated`; el backend es el único con acceso. La *service role* nunca llega al frontend.
- **Límite conocido:** la autenticación del panel es una lista de correos + contraseña compartida por variable de entorno (no Supabase Auth ni contraseñas individuales). Es suficiente para la demo; para producción conviene migrar a cuentas individuales.

### Pruebas

```bash
cd backend && pytest
```

Cubren: búsqueda por ciudad/fechas, evento inexistente, cantidades inválidas (negativas, decimales, fuera de límite), zona ajena, importes, datos desactualizados, zona agotada, clic sin venta, "ya pagué" como pago reportado, confirmación solo por admin, redirecciones abiertas y demo sin claves. Migración SQL y RLS: `supabase/migrations/20261021000000_events.sql` (la app también crea las tablas al arrancar).

### Integraciones

| | Estado |
|---|---|
| Chat web, catálogo, herramientas, panel, CSV | **Real** (código propio) |
| Motor Claude con *tool calling* | **Real**, requiere `ANTHROPIC_API_KEY` (no probado sin la key) |
| Catálogo de eventos de FC Producciones | **Simulado** (eventos ficticios) |
| Disponibilidad y precios de TuEntradaWeb | **Pendiente**: se cargan y verifican a mano en el panel |
| API / webhooks / checkout preseleccionado de TuEntradaWeb | **Pendiente**: no existe integración ni se asume una |
| WhatsApp para eventos | **Pendiente** (ver abajo); el webhook de restaurantes existente no se modificó |

### Conectar después TuEntradaWeb (si FC Producciones obtiene acceso autorizado)

1. Con documentación oficial, crea un cliente en `backend/app/` que sincronice eventos y zonas hacia `events`/`event_zones` (con `verified_at` = hora de la sincronización).
2. Si hay *deep links* documentados, guárdalos como `purchase_url`; no construyas parámetros que no estén documentados.
3. Para confirmar compras de forma verificable, recibe el webhook oficial (valida firma y evita duplicados, como en `/webhook/kapso`) y crea el reporte confirmado con `reviewed_by="integracion:tuentradaweb"`, la referencia y el importe que envíe la plataforma.

### WhatsApp (Zernio / Kapso / Meta)

El motor es independiente del canal; `backend/app/event_whatsapp.py` es el adaptador de WhatsApp y envía por `whatsapp.py`, así que usa el proveedor ya configurado (p. ej. Zernio).

- **Entrada:** el mensaje que empieza el chat lleva la etiqueta `[sabi:eventos]`, por ejemplo con un enlace `https://wa.me/<número>?text=%5Bsabi%3Aeventos%5D%20Hola`. Después, el chat de eventos sigue activo 12 h sin etiqueta. Una etiqueta de restaurante (`[sabi:nacional]`) vuelve al flujo de restaurantes.
- **Webhooks:** los de Zernio (`/webhook/zernio`, firma HMAC) y Kapso ya validan autenticidad; los mensajes se deduplican por el id del proveedor. Para probar sin proveedor, `POST /webhook/simulate` con `{"phone","text"}`.
- **Respuesta:** texto plano; el enlace de compra se arma como `FRONTEND_BASE_URL` + ruta de clic, solo si el evento tiene enlace oficial.
- **Privacidad:** la conversación se identifica con un UUID derivado del número (el número no se guarda en las tablas de eventos).
- Variables necesarias (las mismas del flujo de restaurantes): `ZERNIO_API_KEY`, `ZERNIO_ACCOUNT_ID`, `ZERNIO_WEBHOOK_SECRET`, `WHATSAPP_MOCK_MODE=false`. No hay campañas ni recordatorios salientes.


### Cartelera oficial de TuEntradaWeb

Cuando ningún evento del catálogo tiene enlace de compra propio (por ejemplo, los eventos demo),
Sabi ofrece el botón **"Ver la cartelera y comprar en TuEntradaWeb"**, que abre
`EVENTS_PLATFORM_URL` (por defecto `https://tuentradaweb.com/inicio`) mediante la redirección
registrada `/api/events/go/cartelera`. El destino sale de la configuración, nunca de la petición.
Abrir la cartelera no es una compra ni una reserva; el pago ocurre en TuEntradaWeb. Para
desactivarla, deja `EVENTS_PLATFORM_URL` vacío. No es una integración oficial.
