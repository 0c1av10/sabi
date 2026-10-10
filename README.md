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
| `DATABASE_URL` | `sqlite+aiosqlite:///./sabi.db` local o `postgresql+asyncpg://...` (Supabase) |
| `ANTHROPIC_API_KEY` | API key de Anthropic |
| `ANTHROPIC_MODEL` | Modelo Claude (default: claude-sonnet-4-5) |
| `AGENT_MOCK_MODE` | `true` = agente determinista sin LLM (pruebas sin key) |
| `WHATSAPP_TOKEN` | Token permanente de WhatsApp Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | phone_number_id del número de Meta |
| `WHATSAPP_VERIFY_TOKEN` | Token de verificación del webhook (elegilo vos) |
| `WHATSAPP_MOCK_MODE` | `true` = mensajes salientes solo se loguean |
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
