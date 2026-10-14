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
python -m scripts.seed          # crea restaurante "La Esquina" (slug: la-esquina, PIN: 1234)
uvicorn app.main:app --reload   # http://localhost:8000
```

```bash
cd web
npm install
npm run dev                     # http://localhost:3000 (proxy a :8000)
```

Login del panel: slug `la-esquina`, PIN `1234`.

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

Con `DATABASE_URL` apuntando a Supabase, el backend crea las tablas al arrancar, usa `NullPool` y desactiva el caché de prepared statements de asyncpg (compatible con el pooler en modo session o transaction) y activa RLS en todas las tablas de `public`. Sin políticas, los roles `anon`/`authenticated` de la Data API no ven nada; el backend se conecta como dueño de las tablas. Con `DEMO_AUTOSEED=true` solo se crea "La Esquina" si no existe: los datos ya no se borran.
