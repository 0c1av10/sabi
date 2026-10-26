"use client";
import { useCallback, useEffect, useState } from "react";
import { eventsApi, formatDateTime, toLocalInput } from "../../lib/events";

const focus =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-berenjena";
const input = `w-full rounded-lg border border-berenjena/30 bg-white px-3 py-2 text-sm ${focus}`;
const btn = `rounded-lg bg-coral px-4 py-2 text-sm font-semibold text-berenjena hover:brightness-95 disabled:opacity-50 ${focus}`;
const btnGhost = `rounded-lg border border-berenjena/40 bg-white px-3 py-1.5 text-sm font-medium text-berenjena hover:bg-pistacho/50 ${focus}`;

type AdminZone = {
  id: number;
  name: string;
  price: string;
  price_label: string;
  currency: string;
  availability: string;
  verified_at: string | null;
  needs_verification: boolean;
};
type AdminEvent = {
  id: number;
  slug: string;
  name: string;
  artist: string;
  city: string;
  venue: string;
  starts_at: string;
  timezone: string;
  description: string;
  image_url: string;
  status: string;
  active: boolean;
  purchase_url: string;
  is_demo: boolean;
  zones: AdminZone[];
};
type Metrics = {
  sessions: number;
  interest: number;
  selections: number;
  clicks: number;
  human_requests: number;
  payments_reported_pending: number;
  confirmed_purchases: number;
  confirmed_revenue: { currency: string; total: string }[];
  attribution_note: string;
};
type Purchase = {
  id: number;
  status: string;
  created_at: string;
  session_id: string;
  user_reference: string;
  event: string;
  zone: string;
  quantity: number | null;
  estimated_subtotal: string;
  reviewed_by: string;
  reviewed_at: string;
  confirmed_reference: string;
  confirmed_amount: string;
  note: string;
};
type Activity = { id: number; kind: string; created_at: string; session_id: string; event: string; zone: string; detail: string };
type SessionRow = { id: string; channel: string; created_at: string; updated_at: string; messages: number; stages: string[] };
type ChatLine = { role: string; body: string; created_at: string };

type EventForm = {
  name: string;
  slug: string;
  artist: string;
  city: string;
  venue: string;
  starts_at: string;
  timezone: string;
  description: string;
  image_url: string;
  status: string;
  active: boolean;
  purchase_url: string;
  is_demo: boolean;
};
const emptyEvent: EventForm = {
  name: "", slug: "", artist: "", city: "", venue: "", starts_at: "", timezone: "America/Caracas",
  description: "", image_url: "", status: "borrador", active: true, purchase_url: "", is_demo: false,
};
type ZoneForm = { name: string; price: string; currency: string; availability: string; mark_verified: boolean };
const emptyZone: ZoneForm = { name: "", price: "", currency: "USD", availability: "por_confirmar", mark_verified: false };

const KIND_LABEL: Record<string, string> = {
  interest: "Interés registrado",
  selection: "Selección preparada",
  click: "Clic en enlace de compra",
  payment_reported: "Pago reportado por usuario",
  human_request: "Atención humana",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm text-berenjena">
      <span className="mb-1 block font-medium">{label}</span>
      {children}
    </label>
  );
}

function Login({ onDone }: { onDone: (email: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await eventsApi<{ email: string }>("/admin/login", { method: "POST", body: JSON.stringify({ email, password }) });
      onDone(res.email);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="mx-auto mt-16 max-w-sm space-y-3 rounded-2xl border border-berenjena/15 bg-white p-6 shadow-sm">
      <h1 className="text-xl font-bold text-berenjena">Administración de eventos</h1>
      <Field label="Correo de administrador">
        <input className={input} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </Field>
      <Field label="Contraseña">
        <input className={input} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </Field>
      {error && <p role="alert" className="text-sm font-medium text-berenjena">⚠ {error}</p>}
      <button className={`${btn} w-full`} disabled={busy}>{busy ? "Entrando…" : "Entrar"}</button>
    </form>
  );
}

function Summary({ m }: { m: Metrics | null }) {
  if (!m) return <p className="text-sm">Cargando…</p>;
  const cards: [string, number | string][] = [
    ["Conversaciones", m.sessions],
    ["Con interés registrado", m.interest],
    ["Selecciones preparadas", m.selections],
    ["Clics al enlace oficial", m.clicks],
    ["Pagos reportados por revisar", m.payments_reported_pending],
    ["Solicitudes de atención humana", m.human_requests],
    ["Compras confirmadas (manual)", m.confirmed_purchases],
  ];
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {cards.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-berenjena/15 bg-white p-3">
            <p className="text-xs text-berenjena/80">{label}</p>
            <p className="font-mono text-2xl font-semibold text-berenjena">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-xl border border-berenjena/15 bg-white p-3">
        <p className="text-xs text-berenjena/80">Ingresos confirmados</p>
        {m.confirmed_revenue.length === 0 ? (
          <p className="text-sm font-medium text-berenjena">Sin datos (aún no hay compras confirmadas)</p>
        ) : (
          m.confirmed_revenue.map((r) => (
            <p key={r.currency} className="font-mono text-xl font-semibold text-berenjena">{r.total} <span className="text-xs">{r.currency}</span></p>
          ))
        )}
        <p className="mt-2 text-xs text-berenjena/80">{m.attribution_note}</p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {["activity", "selections", "purchases"].map((k) => (
          <a key={k} className={btnGhost} href={`/api/events/admin/export/${k}.csv`} download>
            Exportar {k === "activity" ? "actividad" : k === "selections" ? "selecciones" : "pagos"} (CSV)
          </a>
        ))}
      </div>
    </div>
  );
}

function EventsTab() {
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [editing, setEditing] = useState<number | null>(null); // null = none, 0 = new
  const [form, setForm] = useState<EventForm>(emptyEvent);
  const [zoneForm, setZoneForm] = useState<ZoneForm>(emptyZone);
  const [editingZone, setEditingZone] = useState<number | null>(null);
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    eventsApi<AdminEvent[]>("/admin/events").then(setEvents).catch((e) => setMsg((e as Error).message));
  }, []);
  useEffect(load, [load]);

  function edit(ev: AdminEvent | null) {
    setMsg("");
    setEditingZone(null);
    setZoneForm(emptyZone);
    if (!ev) {
      setEditing(0);
      setForm(emptyEvent);
      return;
    }
    setEditing(ev.id);
    setForm({
      name: ev.name, slug: ev.slug, artist: ev.artist, city: ev.city, venue: ev.venue,
      starts_at: toLocalInput(ev.starts_at, ev.timezone), timezone: ev.timezone,
      description: ev.description, image_url: ev.image_url, status: ev.status, active: ev.active,
      purchase_url: ev.purchase_url, is_demo: ev.is_demo,
    });
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setMsg("");
    try {
      const body = JSON.stringify({ ...form, slug: form.slug || undefined });
      const saved = editing
        ? await eventsApi<AdminEvent>(`/admin/events/${editing}`, { method: "PUT", body })
        : await eventsApi<AdminEvent>("/admin/events", { method: "POST", body });
      setEditing(saved.id);
      setMsg("Guardado.");
      load();
    } catch (err) {
      setMsg((err as Error).message);
    }
  }

  async function toggleActive(ev: AdminEvent) {
    await eventsApi(`/admin/events/${ev.id}/active`, { method: "POST", body: JSON.stringify({ active: !ev.active }) });
    load();
  }

  async function saveZone(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setMsg("");
    try {
      const body = JSON.stringify(zoneForm);
      if (editingZone) await eventsApi(`/admin/zones/${editingZone}`, { method: "PUT", body });
      else await eventsApi(`/admin/events/${editing}/zones`, { method: "POST", body });
      setZoneForm(emptyZone);
      setEditingZone(null);
      setMsg("Zona guardada.");
      load();
    } catch (err) {
      setMsg((err as Error).message);
    }
  }

  const current = events.find((e) => e.id === editing);
  const [syncing, setSyncing] = useState(false);

  async function syncNow() {
    setSyncing(true);
    setMsg("");
    try {
      const r = await eventsApi<{ created: number; updated: number; total: number; note?: string }>(
        "/admin/sync", { method: "POST" });
      setMsg(r.note || `Sincronizado con TuEntradaWeb: ${r.total} eventos (${r.created} nuevos, ${r.updated} actualizados).`);
      load();
    } catch (err) {
      setMsg((err as Error).message);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
      <section aria-label="Lista de eventos">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-berenjena">Eventos</h2>
          <div className="flex gap-2">
            <button className={btnGhost} onClick={syncNow} disabled={syncing}>
              {syncing ? "Sincronizando…" : "Sincronizar con TuEntradaWeb"}
            </button>
            <button className={btn} onClick={() => edit(null)}>Nuevo evento</button>
          </div>
        </div>
        {msg && <p role="status" className="mb-2 text-sm text-berenjena">{msg}</p>}
        <ul className="space-y-2">
          {events.map((ev) => (
            <li key={ev.id} className="rounded-xl border border-berenjena/15 bg-white p-3 text-sm text-berenjena">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-semibold">{ev.name}{ev.is_demo && <span className="ml-2 rounded-full bg-pistacho px-2 py-0.5 text-xs">demo</span>}</p>
                  <p className="text-xs text-berenjena/80">{ev.city} · {formatDateTime(ev.starts_at)} · {ev.status}{ev.active ? "" : " · desactivado"}</p>
                  <p className="text-xs text-berenjena/80">{ev.purchase_url ? "Enlace oficial configurado" : "Sin enlace de compra"}</p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button className={btnGhost} onClick={() => edit(ev)}>Editar</button>
                  <button className={btnGhost} onClick={() => toggleActive(ev)}>{ev.active ? "Desactivar" : "Activar"}</button>
                </div>
              </div>
            </li>
          ))}
          {events.length === 0 && <li className="text-sm text-berenjena/80">Todavía no hay eventos.</li>}
        </ul>
      </section>

      <section aria-label="Editor de evento">
        {editing === null ? (
          <p className="text-sm text-berenjena/80">Elige un evento o crea uno nuevo.</p>
        ) : (
          <div className="space-y-6">
            <form onSubmit={save} className="space-y-3 rounded-2xl border border-berenjena/15 bg-white p-4">
              <h2 className="text-lg font-semibold text-berenjena">{editing ? "Editar evento" : "Nuevo evento"}</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Nombre"><input className={input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
                <Field label="Artista"><input className={input} value={form.artist} onChange={(e) => setForm({ ...form, artist: e.target.value })} /></Field>
                <Field label="Ciudad"><input className={input} value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required /></Field>
                <Field label="Recinto"><input className={input} value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} /></Field>
                <Field label="Fecha y hora (hora del evento)"><input className={input} type="datetime-local" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} required /></Field>
                <Field label="Zona horaria (IANA)"><input className={input} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} required /></Field>
                <Field label="Estado">
                  <select className={input} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                    {["borrador", "publicado", "cancelado", "finalizado"].map((s) => <option key={s}>{s}</option>)}
                  </select>
                </Field>
                <Field label="Slug (opcional)"><input className={input} value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} pattern="[a-z0-9-]{3,120}" /></Field>
              </div>
              <Field label="Descripción"><textarea className={input} rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
              <Field label="Imagen (URL https, opcional)"><input className={input} value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} /></Field>
              <Field label="Enlace oficial de compra verificado (https)">
                <input className={input} value={form.purchase_url} onChange={(e) => setForm({ ...form, purchase_url: e.target.value })} placeholder="https://…" disabled={form.is_demo} />
              </Field>
              <p className="text-xs text-berenjena/80">Pega solo el enlace que la plataforma de venta haya confirmado. Sabi no construye enlaces de checkout. Vacío = compra deshabilitada.</p>
              <div className="flex flex-wrap gap-4 text-sm text-berenjena">
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} /> Activo</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.is_demo} onChange={(e) => setForm({ ...form, is_demo: e.target.checked, purchase_url: e.target.checked ? "" : form.purchase_url })} /> Datos de demostración (sin compra externa)</label>
              </div>
              <button className={btn}>Guardar evento</button>
            </form>

            {editing ? (
              <div className="rounded-2xl border border-berenjena/15 bg-white p-4">
                <h3 className="text-base font-semibold text-berenjena">Zonas y precios de referencia</h3>
                <ul className="mt-2 space-y-1 text-sm text-berenjena">
                  {current?.zones.map((z) => (
                    <li key={z.id} className="flex items-center justify-between gap-2 rounded-lg bg-crema px-3 py-2">
                      <span>
                        <strong>{z.name}</strong> · {z.price_label} · {z.availability}
                        <span className="block text-xs text-berenjena/80">
                          {z.verified_at ? `Verificada ${formatDateTime(z.verified_at)}` : "Nunca verificada"}
                          {z.needs_verification ? " · requiere verificación" : ""}
                        </span>
                      </span>
                      <button className={btnGhost} onClick={() => { setEditingZone(z.id); setZoneForm({ name: z.name, price: z.price, currency: z.currency, availability: z.availability, mark_verified: false }); }}>Editar</button>
                    </li>
                  ))}
                </ul>
                <form onSubmit={saveZone} className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Field label="Nombre de la zona"><input className={input} value={zoneForm.name} onChange={(e) => setZoneForm({ ...zoneForm, name: e.target.value })} required /></Field>
                  <Field label="Precio de referencia"><input className={input} inputMode="decimal" value={zoneForm.price} onChange={(e) => setZoneForm({ ...zoneForm, price: e.target.value })} required placeholder="25.00" /></Field>
                  <Field label="Moneda">
                    <select className={input} value={zoneForm.currency} onChange={(e) => setZoneForm({ ...zoneForm, currency: e.target.value })}>
                      {["USD", "EUR", "VES"].map((c) => <option key={c}>{c}</option>)}
                    </select>
                  </Field>
                  <Field label="Estado informado">
                    <select className={input} value={zoneForm.availability} onChange={(e) => setZoneForm({ ...zoneForm, availability: e.target.value })}>
                      {["disponible", "agotado", "por_confirmar"].map((c) => <option key={c}>{c}</option>)}
                    </select>
                  </Field>
                  <label className="flex items-center gap-2 text-sm text-berenjena sm:col-span-2">
                    <input type="checkbox" checked={zoneForm.mark_verified} onChange={(e) => setZoneForm({ ...zoneForm, mark_verified: e.target.checked })} />
                    Acabo de verificar este precio y estado en la plataforma de venta
                  </label>
                  <div className="flex gap-2 sm:col-span-2">
                    <button className={btn}>{editingZone ? "Guardar zona" : "Agregar zona"}</button>
                    {editingZone && <button type="button" className={btnGhost} onClick={() => { setEditingZone(null); setZoneForm(emptyZone); }}>Cancelar</button>}
                  </div>
                </form>
              </div>
            ) : (
              <p className="text-sm text-berenjena/80">Guarda el evento para agregar zonas.</p>
            )}
            {msg && <p role="status" className="text-sm font-medium text-berenjena">{msg}</p>}
          </div>
        )}
      </section>
    </div>
  );
}

function PurchasesTab({ admin }: { admin: string }) {
  const [rows, setRows] = useState<Purchase[]>([]);
  const [msg, setMsg] = useState("");
  const [forms, setForms] = useState<Record<number, { reference: string; amount: string; currency: string; note: string }>>({});
  const load = useCallback(() => {
    eventsApi<Purchase[]>("/admin/purchases").then(setRows).catch((e) => setMsg((e as Error).message));
  }, []);
  useEffect(load, [load]);
  const f = (id: number) => forms[id] ?? { reference: "", amount: "", currency: "USD", note: "" };
  const set = (id: number, patch: Partial<ReturnType<typeof f>>) => setForms({ ...forms, [id]: { ...f(id), ...patch } });

  async function confirm(id: number) {
    setMsg("");
    try {
      await eventsApi(`/admin/purchases/${id}/confirm`, { method: "POST", body: JSON.stringify(f(id)) });
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }
  async function reject(id: number) {
    setMsg("");
    try {
      await eventsApi(`/admin/purchases/${id}/reject`, { method: "POST", body: JSON.stringify({ note: f(id).note }) });
      load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  const pending = rows.filter((r) => r.status === "reported");
  const done = rows.filter((r) => r.status !== "reported");
  return (
    <div className="space-y-6">
      <section aria-label="Pagos reportados pendientes">
        <h2 className="text-lg font-semibold text-berenjena">Pagos reportados pendientes de revisión</h2>
        <p className="text-sm text-berenjena/80">Un “ya pagué” no es un pago confirmado. Confírmalo solo después de verificarlo en la plataforma de venta o con el comprobante. Quedará registrado a nombre de {admin}.</p>
        {msg && <p role="alert" className="mt-2 text-sm font-medium text-berenjena">⚠ {msg}</p>}
        <ul className="mt-3 space-y-3">
          {pending.map((r) => (
            <li key={r.id} className="rounded-xl border border-berenjena/15 bg-white p-3 text-sm text-berenjena">
              <p className="font-semibold">{r.event || "Sin evento asociado"}{r.zone ? ` · ${r.zone}` : ""}{r.quantity ? ` × ${r.quantity}` : ""}</p>
              <p className="text-xs text-berenjena/80">Reportado {formatDateTime(r.created_at)} · referencia del usuario: {r.user_reference || "(ninguna)"} · {r.estimated_subtotal ? `subtotal orientativo ${r.estimated_subtotal}` : "sin selección vinculada"}</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-4">
                <input aria-label="Referencia verificada" className={input} placeholder="Referencia verificada" value={f(r.id).reference} onChange={(e) => set(r.id, { reference: e.target.value })} />
                <input aria-label="Importe confirmado" className={input} inputMode="decimal" placeholder="Importe" value={f(r.id).amount} onChange={(e) => set(r.id, { amount: e.target.value })} />
                <select aria-label="Moneda" className={input} value={f(r.id).currency} onChange={(e) => set(r.id, { currency: e.target.value })}>{["USD", "EUR", "VES"].map((c) => <option key={c}>{c}</option>)}</select>
                <input aria-label="Nota" className={input} placeholder="Nota" value={f(r.id).note} onChange={(e) => set(r.id, { note: e.target.value })} />
              </div>
              <div className="mt-2 flex gap-2">
                <button className={btn} onClick={() => confirm(r.id)}>Confirmar compra (manual)</button>
                <button className={btnGhost} onClick={() => reject(r.id)}>Rechazar</button>
              </div>
            </li>
          ))}
          {pending.length === 0 && <li className="text-sm text-berenjena/80">No hay pagos reportados por revisar.</li>}
        </ul>
      </section>
      <section aria-label="Revisados">
        <h2 className="text-lg font-semibold text-berenjena">Revisados</h2>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm text-berenjena">
            <thead><tr className="border-b border-berenjena/20 text-xs"><th className="py-1 pr-2">Estado</th><th className="pr-2">Evento / zona</th><th className="pr-2">Referencia</th><th className="pr-2">Importe</th><th className="pr-2">Revisó</th><th>Fecha</th></tr></thead>
            <tbody>
              {done.map((r) => (
                <tr key={r.id} className="border-b border-berenjena/10">
                  <td className="py-1 pr-2">{r.status === "confirmed" ? "Confirmada (atribución manual)" : "Rechazada"}</td>
                  <td className="pr-2">{r.event} {r.zone}</td>
                  <td className="pr-2 font-mono">{r.confirmed_reference}</td>
                  <td className="pr-2 font-mono">{r.confirmed_amount}</td>
                  <td className="pr-2">{r.reviewed_by}</td>
                  <td>{formatDateTime(r.reviewed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ActivityTab() {
  const [rows, setRows] = useState<Activity[]>([]);
  const [kind, setKind] = useState("");
  useEffect(() => {
    eventsApi<Activity[]>(`/admin/activity${kind ? `?kind=${kind}` : ""}`).then(setRows).catch(() => setRows([]));
  }, [kind]);
  return (
    <section aria-label="Actividad">
      <div className="mb-3 flex items-center gap-3">
        <h2 className="text-lg font-semibold text-berenjena">Actividad</h2>
        <select aria-label="Filtrar por tipo" className={`${input} max-w-xs`} value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">Todos</option>
          {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <p className="mb-2 text-xs text-berenjena/80">Un clic solo indica que se abrió el enlace oficial; no es una compra.</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm text-berenjena">
          <thead><tr className="border-b border-berenjena/20 text-xs"><th className="py-1 pr-2">Fecha</th><th className="pr-2">Tipo</th><th className="pr-2">Evento</th><th className="pr-2">Zona</th><th className="pr-2">Detalle</th><th>Conversación</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-berenjena/10">
                <td className="py-1 pr-2">{formatDateTime(r.created_at)}</td>
                <td className="pr-2">{KIND_LABEL[r.kind] ?? r.kind}</td>
                <td className="pr-2">{r.event}</td>
                <td className="pr-2">{r.zone}</td>
                <td className="pr-2">{r.detail}</td>
                <td className="font-mono text-xs">{r.session_id.slice(0, 8)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SessionsTab() {
  const [rows, setRows] = useState<SessionRow[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [lines, setLines] = useState<ChatLine[]>([]);
  useEffect(() => {
    eventsApi<SessionRow[]>("/admin/sessions").then(setRows).catch(() => setRows([]));
  }, []);
  async function view(id: string) {
    setOpen(id);
    setLines(await eventsApi<ChatLine[]>(`/admin/sessions/${id}/messages`));
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section aria-label="Conversaciones">
        <h2 className="mb-2 text-lg font-semibold text-berenjena">Conversaciones</h2>
        <ul className="space-y-2">
          {rows.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-2 rounded-xl border border-berenjena/15 bg-white p-3 text-sm text-berenjena">
              <span>
                <span className="font-mono text-xs">{s.id.slice(0, 8)}</span> · {s.messages} mensajes · {formatDateTime(s.updated_at)}
                <span className="block text-xs text-berenjena/80">{s.stages.map((k) => KIND_LABEL[k] ?? k).join(" · ") || "Sin actividad comercial"}</span>
              </span>
              <button className={btnGhost} onClick={() => view(s.id)}>Ver</button>
            </li>
          ))}
        </ul>
      </section>
      <section aria-label="Mensajes">
        {open && (
          <div className="space-y-2 rounded-xl border border-berenjena/15 bg-white p-3 text-sm text-berenjena">
            {lines.map((l, i) => (
              <p key={i}><strong>{l.role === "user" ? "Usuario" : "Sabi"}:</strong> <span className="whitespace-pre-line">{l.body}</span></p>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

type GymProfile = { name: string; address: string; classes_text: string; schedule_text: string; membership_text: string; contact: string; owner_phone: string; calendar_id: string; calendar_ready?: boolean; calendar_share_with?: string };
type GymRequest = { id: number; phone: string; student_name: string; level: string; preferred: string; status: string; gym_note: string; created_at: string; reviewed_by: string; starts_at: string | null; calendar_link: string };
const emptyGym: GymProfile = { name: "", address: "", classes_text: "", schedule_text: "", membership_text: "", contact: "", owner_phone: "", calendar_id: "" };

function GymTab() {
  const [profile, setProfile] = useState<GymProfile>(emptyGym);
  const [rows, setRows] = useState<GymRequest[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [slots, setSlots] = useState<Record<number, { at: string; mins: string }>>({});
  const [clash, setClash] = useState<number | null>(null);
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    eventsApi<GymProfile>("/admin/gym/profile").then(setProfile).catch((e) => setMsg((e as Error).message));
    eventsApi<GymRequest[]>("/admin/gym/requests").then(setRows).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setMsg("");
    try {
      setProfile(await eventsApi<GymProfile>("/admin/gym/profile", { method: "PUT", body: JSON.stringify(profile) }));
      setMsg("Datos del gimnasio guardados.");
    } catch (err) {
      setMsg((err as Error).message);
    }
  }
  async function review(id: number, action: "confirm" | "reject", force = false) {
    setMsg("");
    setClash(null);
    const slot = slots[id];
    const body: Record<string, unknown> = { note: notes[id] || "", force };
    if (action === "confirm" && slot?.at) {
      body.starts_at = slot.at;
      body.duration_minutes = Number(slot.mins) || 60;
    }
    try {
      await eventsApi(`/admin/gym/requests/${id}/${action}`, { method: "POST", body: JSON.stringify(body) });
      setMsg(action === "confirm" ? "Confirmada: el alumno recibió el mensaje." : "Rechazada: el alumno fue avisado.");
      load();
    } catch (err) {
      const text = (err as Error).message;
      setMsg(text);
      if (text.startsWith("Ese horario choca")) setClash(id);
    }
  }
  const set = (k: keyof GymProfile) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setProfile({ ...profile, [k]: e.target.value });

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
      <section aria-label="Datos del gimnasio">
        <h2 className="mb-3 text-lg font-semibold">Datos del gimnasio</h2>
        <p className="mb-3 text-xs text-berenjena/80">Sabi solo dice lo que escribas aquí. Lo vacío lo confirma el gimnasio.</p>
        <form onSubmit={saveProfile} className="space-y-3 rounded-xl border border-berenjena/15 bg-white p-4 text-sm">
          <Field label="Nombre"><input className={input} value={profile.name} onChange={set("name")} /></Field>
          <Field label="Dirección"><input className={input} value={profile.address} onChange={set("address")} /></Field>
          <Field label="Clases que ofrece"><textarea className={input} rows={2} value={profile.classes_text} onChange={set("classes_text")} /></Field>
          <Field label="Horarios"><textarea className={input} rows={2} value={profile.schedule_text} onChange={set("schedule_text")} /></Field>
          <Field label="Mensualidad (como la comunica el gimnasio)"><textarea className={input} rows={2} value={profile.membership_text} onChange={set("membership_text")} /></Field>
          <Field label="Contacto"><input className={input} value={profile.contact} onChange={set("contact")} /></Field>
          <Field label="WhatsApp que recibe cada solicitud (con código de país)"><input className={input} value={profile.owner_phone} onChange={set("owner_phone")} /></Field>
          <Field label="ID del Google Calendar del gimnasio">
            <input className={input} value={profile.calendar_id} onChange={set("calendar_id")} placeholder="ej. clases@group.calendar.google.com" />
          </Field>
          <p className="text-xs text-berenjena/80">
            {profile.calendar_ready
              ? `Para conectar: en Google Calendar, comparte ese calendario con ${profile.calendar_share_with} con permiso «Hacer cambios en eventos». Cada clase confirmada se agrega sola y Sabi avisa si el horario choca.`
              : "Google Calendar todavía no está configurado en el servidor."}
          </p>
          <button className={btn} type="submit">Guardar</button>
        </form>
      </section>
      <section aria-label="Solicitudes de clase">
        <h2 className="mb-3 text-lg font-semibold">Solicitudes de clase</h2>
        {msg && <p role="status" className="mb-2 text-sm">{msg}</p>}
        <ul className="space-y-2">
          {rows.length === 0 && <li className="text-sm text-berenjena/80">Todavía no hay solicitudes.</li>}
          {rows.map((r) => (
            <li key={r.id} className="rounded-xl border border-berenjena/15 bg-white p-3 text-sm">
              <p className="font-semibold">{r.student_name} <span className="font-normal text-berenjena/80">· {r.level} · +{r.phone}</span></p>
              <p className="text-xs text-berenjena/80">Prefiere: {r.preferred} · {formatDateTime(r.created_at)} · {r.status}</p>
              {r.status === "solicitada" ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  <input type="datetime-local" className={`${input} w-auto`} aria-label="Día y hora de la clase"
                    value={slots[r.id]?.at || ""} onChange={(e) => setSlots({ ...slots, [r.id]: { at: e.target.value, mins: slots[r.id]?.mins || "60" } })} />
                  <select className={`${input} w-auto`} aria-label="Duración"
                    value={slots[r.id]?.mins || "60"} onChange={(e) => setSlots({ ...slots, [r.id]: { at: slots[r.id]?.at || "", mins: e.target.value } })}>
                    {["45", "60", "90", "120"].map((m) => <option key={m} value={m}>{m} min</option>)}
                  </select>
                  <input className={`${input} flex-1`} placeholder="Nota para el alumno (opcional)" aria-label="Nota para el alumno"
                    value={notes[r.id] || ""} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })} />
                  <button className={btn} onClick={() => review(r.id, "confirm")}>Confirmar</button>
                  {clash === r.id && <button className={btnGhost} onClick={() => review(r.id, "confirm", true)}>Confirmar igual</button>}
                  <button className={btnGhost} onClick={() => review(r.id, "reject")}>Rechazar</button>
                </div>
              ) : (
                <p className="mt-1 text-xs">Revisada por {r.reviewed_by}: {r.gym_note || (r.starts_at ? formatDateTime(r.starts_at) : "—")}{r.calendar_link && <> · <a className="underline" href={r.calendar_link} target="_blank" rel="noreferrer">Ver en Google Calendar</a></>}</p>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

const TABS = ["Resumen", "Eventos", "Clases", "Pagos reportados", "Actividad", "Conversaciones"] as const;

export default function AdminPanel() {
  const [admin, setAdmin] = useState<string | null | undefined>(undefined); // undefined = checking
  const [tab, setTab] = useState<(typeof TABS)[number]>("Resumen");
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  useEffect(() => {
    eventsApi<{ email: string }>("/admin/me").then((r) => setAdmin(r.email)).catch(() => setAdmin(null));
  }, []);
  useEffect(() => {
    if (admin && tab === "Resumen") eventsApi<Metrics>("/admin/metrics").then(setMetrics).catch(() => setMetrics(null));
  }, [admin, tab]);

  if (admin === undefined) return <p className="p-6 text-sm text-berenjena">Cargando…</p>;
  if (!admin) return <div className="min-h-screen bg-crema px-4"><Login onDone={setAdmin} /></div>;

  async function logout() {
    await eventsApi("/admin/logout", { method: "POST" }).catch(() => undefined);
    setAdmin(null);
  }

  return (
    <div className="min-h-screen bg-crema text-berenjena">
      <header className="border-b border-berenjena/15 px-4 py-3">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2">
          <h1 className="text-lg font-bold">Sabi — Administración de eventos <span className="ml-2 rounded-full bg-pistacho px-2 py-0.5 text-xs">Demo</span></h1>
          <div className="flex items-center gap-3 text-sm">
            <span>{admin}</span>
            <button className={btnGhost} onClick={logout}>Salir</button>
          </div>
        </div>
        <nav aria-label="Secciones" className="mx-auto mt-3 flex max-w-6xl flex-wrap gap-2">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)} aria-current={tab === t ? "page" : undefined}
              className={`rounded-full px-4 py-1.5 text-sm font-medium ${focus} ${tab === t ? "bg-berenjena text-crema" : "border border-berenjena/30 bg-white"}`}>
              {t}
            </button>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        {tab === "Resumen" && <Summary m={metrics} />}
        {tab === "Eventos" && <EventsTab />}
        {tab === "Clases" && <GymTab />}
        {tab === "Pagos reportados" && <PurchasesTab admin={admin} />}
        {tab === "Actividad" && <ActivityTab />}
        {tab === "Conversaciones" && <SessionsTab />}
      </main>
    </div>
  );
}
