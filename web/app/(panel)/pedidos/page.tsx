"use client";
import { useEffect, useRef, useState } from "react";
import Mascot from "../../../components/Mascot";
import { api } from "../../../lib/api";
import { bs, eur, usd, type Rates } from "../../../lib/money";

type OrderItem = { id: number; name: string; quantity: number; unit_price: number; extras: string; notes: string };
type Order = {
  id: number; status: string; order_type: string; address: string; notes: string;
  total: number; delivery_fee?: number; delivery_zone?: string; source?: string; customer_phone: string; customer_name: string; created_at: string;
  payment_status: string; payment_method: string; payment_reference: string; rejection_reason?: string;
  items: OrderItem[];
};
type Today = {
  orders_total: number; approved: number; rejected: number; pending: number; open_conversations: number;
  sales_today?: number; avg_ticket?: number; unpaid_approved?: number;
  top_items?: { name: string; quantity: number }[]; day?: string;
};
type Me = { name: string; slug: string; exchange_rate: number; eur_rate: number; rates_date?: string | null };

const paymentLabel: Record<string, string> = {
  pago_movil: "Pago móvil", zelle: "Zelle", transferencia: "Transferencia", efectivo: "Efectivo",
};
const statusStyle: Record<string, [string, string]> = {
  pending: ["pendiente", "bg-amber-100 text-amber-800"],
  approved: ["aprobado", "bg-emerald-100 text-emerald-800"],
  edited: ["editado y aprobado", "bg-emerald-100 text-emerald-800"],
  rejected: ["rechazado", "bg-red-100 text-red-700"],
};

// Stored times are naive UTC: read them as UTC and show them in Caracas time.
const asUtc = (iso: string) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
const caracasDay = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: "America/Caracas" });
const hhmm = (iso: string) => asUtc(iso).toLocaleTimeString("es-VE", { hour: "2-digit", minute: "2-digit", timeZone: "America/Caracas" });
function ago(iso: string) {
  const min = Math.max(0, Math.round((Date.now() - asUtc(iso).getTime()) / 60000));
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  return h < 24 ? `hace ${h} h` : `hace ${Math.floor(h / 24)} d`;
}

function Stat({ label, value, sub, tone = "" }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className={`rounded-xl border bg-white p-4 ${tone}`}>
      <p className="text-xs text-stone-500">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight">{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-stone-500">{sub}</p>}
    </div>
  );
}

export default function Pedidos() {
  const [pending, setPending] = useState<Order[]>([]);
  const [all, setAll] = useState<Order[]>([]);
  const [today, setToday] = useState<Today | null>(null);
  const [tab, setTab] = useState<"pending" | "today">("pending");
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [copied, setCopied] = useState(false);
  const seen = useRef<number | null>(null);
  const rate: Rates = { usd: me?.exchange_rate ?? 0, eur: me?.eur_rate ?? 0 };

  useEffect(() => { api("/me").then(setMe).catch(() => {}); }, []);

  async function load() {
    try {
      const [p, a] = await Promise.all([api("/orders?status=pending"), api("/orders")]);
      setPending(p);
      setAll(a);
      setError("");
    } catch (e) {
      setError("No autenticado. Entrá desde /login.");
    }
    api("/today").then(setToday).catch(() => {});
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  // A pending order shows in the tab title so it is noticed from another tab.
  useEffect(() => {
    document.title = pending.length ? `(${pending.length}) Sabi · pedidos` : "Sabi · pedidos";
    if (seen.current !== null && pending.length > seen.current) setTab("pending");
    seen.current = pending.length;
  }, [pending.length]);

  async function act(id: number, action: string, body?: object) {
    await api(`/orders/${id}/${action}`, { method: "POST", body: JSON.stringify(body ?? {}) });
    setRejecting(null);
    setReason("");
    load();
  }

  const todayKey = caracasDay(new Date());
  const decidedToday = all.filter((o) => o.status !== "pending" && caracasDay(asUtc(o.created_at)) === todayKey);
  const link = me ? `${typeof window !== "undefined" ? window.location.origin : "https://www.holasabi.com"}/tienda/${me.slug}` : "";
  const money = (v: number) => (
    <>{usd(v)}<span className="ml-2 text-xs font-normal text-stone-500">{eur(v, rate)} · {bs(v, rate)}</span></>
  );

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">{me ? `Hola, ${me.name}` : "Pedidos"}</h1>
          <p className="text-sm text-stone-500">
            {new Date().toLocaleDateString("es-VE", { weekday: "long", day: "numeric", month: "long", timeZone: "America/Caracas" })}
            {me?.rates_date && <span> · tasa BCV {me.rates_date.split("-").reverse().join("/")}: $1 = {bs(1, rate)}</span>}
          </p>
        </div>
        {link && (
          <button onClick={() => { navigator.clipboard?.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 1800); }}
            className="rounded-full border bg-white px-4 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-100">
            {copied ? "¡Enlace copiado!" : "Copiar el enlace de tu tienda"}
          </button>
        )}
      </div>

      {today && (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Pedidos hoy" value={String(today.orders_total)} sub={`${today.approved} aprobados · ${today.rejected} rechazados`} />
          <Stat label="Ventas de hoy" value={usd(today.sales_today ?? 0)} sub={`${eur(today.sales_today ?? 0, rate)} · ${bs(today.sales_today ?? 0, rate)}`} />
          <Stat label="Ticket promedio" value={usd(today.avg_ticket ?? 0)} sub={today.approved ? `en ${today.approved} pedidos aprobados` : "aún sin pedidos aprobados"} />
          <Stat label="Por aprobar" value={String(pending.length)}
            sub={today.unpaid_approved ? `${today.unpaid_approved} aprobados con pago por verificar` : "todo al día"}
            tone={pending.length ? "border-amber-300 bg-amber-50" : ""} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <section>
          <div className="mb-4 flex gap-2 text-sm" role="tablist">
            {([["pending", `Por aprobar (${pending.length})`], ["today", `Atendidos hoy (${decidedToday.length})`]] as const).map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                className={`rounded-full px-4 py-1.5 font-medium ${tab === k ? "bg-emerald-700 text-white" : "border bg-white text-stone-600 hover:bg-stone-100"}`}>
                {label}
              </button>
            ))}
          </div>
          {error && <p className="text-red-600">{error}</p>}

          {tab === "pending" && (
            <>
              {pending.length === 0 && !error && (
                <div className="flex flex-col items-center gap-3 rounded-xl border bg-white py-12 text-center text-stone-500">
                  <Mascot pose="idle" className="w-24" />
                  <p>No hay pedidos por aprobar. Sabi te avisa cuando entre uno.</p>
                </div>
              )}
              <div className="space-y-4">
                {pending.map((o) => (
                  <div key={o.id} className="rounded-xl border-2 border-amber-300 bg-white p-4 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">Pedido #{o.id} — {money(o.total)}
                          {!!o.delivery_fee && <span className="ml-2 text-xs font-normal text-stone-500">incluye delivery{o.delivery_zone ? ` ${o.delivery_zone}` : ""} {usd(o.delivery_fee)}</span>}</p>
                        <p className="text-sm text-stone-500">
                          {o.source === "tienda" ? "Tienda web · " : "WhatsApp · "}{o.customer_name || o.customer_phone} · {o.order_type}
                          {o.address ? ` · ${o.address}` : ""} · {hhmm(o.created_at)} ({ago(o.created_at)})
                        </p>
                        <p className="mt-1 text-sm">
                          Pago: <strong>{paymentLabel[o.payment_method] || o.payment_method || "No indicado"}</strong>
                          {o.payment_reference && <span className="text-stone-500"> · Ref. {o.payment_reference}</span>}
                          {" · "}
                          <span className={o.payment_status === "confirmed" ? "text-emerald-700" : "text-amber-700"}>
                            {o.payment_status === "confirmed" ? "pago confirmado" : "por verificar"}
                          </span>
                        </p>
                      </div>
                      <span className="shrink-0 rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800">pendiente</span>
                    </div>
                    <ul className="mt-2 text-sm">
                      {o.items.map((i) => (
                        <li key={i.id}>
                          {i.quantity} × {i.name} — {usd(i.unit_price * i.quantity)}
                          <span className="text-stone-400"> · {eur(i.unit_price * i.quantity, rate)} · {bs(i.unit_price * i.quantity, rate)}</span>
                          {i.extras && <span className="text-stone-500"> ({i.extras})</span>}
                        </li>
                      ))}
                    </ul>
                    {o.notes && <p className="mt-1 text-sm text-stone-500">Notas: {o.notes}</p>}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {o.payment_status !== "confirmed" && (
                        <button onClick={() => act(o.id, "confirm-payment")}
                          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white">
                          Confirmar pago
                        </button>
                      )}
                      <button onClick={() => act(o.id, "approve")}
                        className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white">
                        Aprobar
                      </button>
                      <button onClick={() => act(o.id, "edit", { edit_summary: "Editado desde el panel" })}
                        className="rounded bg-stone-200 px-3 py-1.5 text-sm font-medium">
                        Editar y aprobar
                      </button>
                      {rejecting === o.id ? (
                        <span className="flex items-center gap-2">
                          <input className="rounded border p-1 text-sm" placeholder="Motivo"
                                 value={reason} onChange={(e) => setReason(e.target.value)} />
                          <button onClick={() => act(o.id, "reject", { reason })}
                            className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white">
                            Confirmar rechazo
                          </button>
                        </span>
                      ) : (
                        <button onClick={() => setRejecting(o.id)}
                          className="rounded bg-red-100 px-3 py-1.5 text-sm font-medium text-red-700">
                          Rechazar
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {tab === "today" && (
            <div className="space-y-3">
              {decidedToday.length === 0 && !error && (
                <p className="rounded-xl border bg-white p-6 text-center text-stone-500">Todavía no has atendido pedidos hoy.</p>
              )}
              {decidedToday.map((o) => {
                const [label, cls] = statusStyle[o.status] || [o.status, "bg-stone-100 text-stone-700"];
                return (
                  <div key={o.id} className="rounded-xl border bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">Pedido #{o.id} — {money(o.total)}</p>
                        <p className="text-sm text-stone-500">
                          {o.customer_name || o.customer_phone} · {o.order_type} · {hhmm(o.created_at)}
                        </p>
                        <p className="mt-1 text-sm text-stone-600">{o.items.map((i) => `${i.quantity} × ${i.name}`).join(", ")}</p>
                        {o.status === "rejected" && o.rejection_reason && <p className="mt-1 text-xs text-red-700">Motivo: {o.rejection_reason}</p>}
                        {o.status !== "rejected" && o.payment_status !== "confirmed" && (
                          <button onClick={() => act(o.id, "confirm-payment")}
                            className="mt-2 rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white">
                            Confirmar pago
                          </button>
                        )}
                      </div>
                      <span className={`shrink-0 rounded px-2 py-1 text-xs font-medium ${cls}`}>{label}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <div className="rounded-xl border bg-white p-5">
            <p className="font-semibold">Copiloto</p>
            <div className="mt-4 space-y-4 text-sm">
              <div>
                <p className="text-xs text-stone-500">Lo más pedido (últimos 7 días)</p>
                {today?.top_items?.length ? (
                  <ol className="mt-1 space-y-1">
                    {today.top_items.map((t, i) => (
                      <li key={t.name} className="flex items-center justify-between gap-2">
                        <span className="truncate"><span className="mr-2 text-stone-400">{i + 1}</span>{t.name}</span>
                        <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">{t.quantity}</span>
                      </li>
                    ))}
                  </ol>
                ) : <p className="mt-1 text-stone-500">Aún no hay pedidos aprobados esta semana.</p>}
              </div>
              <div>
                <p className="text-xs text-stone-500">Conversaciones abiertas hoy</p>
                <p className="text-2xl font-bold tabular-nums">{today?.open_conversations ?? 0}</p>
              </div>
              {!!today?.unpaid_approved && (
                <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  Tienes {today.unpaid_approved} {today.unpaid_approved === 1 ? "pedido aprobado" : "pedidos aprobados"} con el pago sin confirmar. Revísalos en «Atendidos hoy».
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
