export type Zone = {
  id: number;
  nombre: string;
  precio_referencia: string;
  precio_minor: number;
  moneda: string;
  estado_informado: string;
  estado: string;
  requiere_verificacion: boolean;
  recomendable: boolean;
  verificado_el: string | null;
};

export type EventData = {
  id: number;
  nombre: string;
  artista: string;
  ciudad: string;
  recinto: string;
  fecha: string;
  descripcion: string;
  imagen: string;
  estado: string;
  demo: boolean;
  compra_habilitada: boolean;
  zonas?: Zone[];
};

export type Block =
  | { type: "events"; events: EventData[] }
  | { type: "event"; event: EventData }
  | {
      type: "selection";
      selection_id: string;
      evento: string;
      evento_id: number;
      zona: string;
      zona_id: number;
      cantidad: number;
      precio_unitario: string;
      subtotal: string;
      moneda: string;
      nota: string;
      advertencias: string[];
      aviso: string;
    }
  | { type: "link"; habilitado: boolean; ruta?: string; texto_boton?: string; mensaje?: string; aviso?: string }
  | { type: "human"; mensaje: string }
  | { type: "payment_reported"; mensaje: string };

export type Status = {
  engine: "demo" | "claude";
  demo_data: boolean;
  events: number;
  purchase_links_enabled: number;
  max_quantity: number;
  stale_hours: number;
  notice: string;
};

export type ChatResponse = { session_id: string; reply: string; ui: Block[]; engine: string };
export type SelectResponse = { session_id: string; ok: boolean; error?: string; mensaje?: string; ui: Block[] };

/** Same-origin call to the events API (cookies carry the admin session). */
export async function eventsApi<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/events${path}`, {
    credentials: "same-origin",
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? "");
    } catch {
      /* non-JSON error body */
    }
    const err = new Error(detail || `Error ${res.status}`) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

export function formatDateTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString("es-VE", { dateStyle: "short", timeStyle: "short" });
}

/** UTC ISO instant -> value for <input type="datetime-local"> in the event's own time zone. */
export function toLocalInput(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}
