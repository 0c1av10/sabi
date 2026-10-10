"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { usd, eur, bs, Rates } from "../../../lib/money";

type Order = { status: string; total: number; items: { name: string; quantity: number }[] };
type Item = { name: string; category: string; available: boolean };

function Copiloto() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [menu, setMenu] = useState<Item[]>([]);
  const [me, setMe] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api("/orders").then(setOrders).catch(() => {});
    api("/menu").then(setMenu).catch(() => {});
    api("/me").then(setMe).catch(() => {});
  }, []);

  if (!me) return null;
  const rates: Rates = { usd: me.exchange_rate, eur: me.eur_rate };
  const valid = orders.filter((o) => o.status !== "rejected");
  const avg = valid.length ? valid.reduce((a, o) => a + o.total, 0) / valid.length : 0;
  const cat = Object.fromEntries(menu.map((m) => [m.name, m.category]));
  const counts: Record<string, number> = {};
  valid.forEach((o) => o.items.forEach((i) => (counts[i.name] = (counts[i.name] || 0) + i.quantity)));
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  const withDessert = valid.filter((o) => o.items.some((i) => cat[i.name] === "Postres")).length;
  const dessert = menu.find((m) => m.category === "Postres" && m.available);
  const phone = (me.owner_phone || "").replace(/\D/g, "");
  const link = `https://wa.me/${phone}?text=${encodeURIComponent(`Hola ${me.name}, quiero hacer un pedido`)}`;

  return (
    <div className="mb-8 rounded-2xl border bg-white p-5">
      <h2 className="font-semibold">Copiloto</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div>
          <p className="text-xs text-stone-500">Ticket promedio</p>
          <p className="mt-1 text-xl font-bold">{usd(avg)}</p>
          <p className="text-xs text-stone-500">{eur(avg, rates)} · {bs(avg, rates)}</p>
        </div>
        <div>
          <p className="text-xs text-stone-500">Lo más pedido</p>
          <p className="mt-1 text-xl font-bold">{top ? top[0] : "—"}</p>
          <p className="text-xs text-stone-500">{top ? `${top[1]} unidades` : "Sin pedidos aún"}</p>
        </div>
        <div>
          <p className="text-xs text-stone-500">Qué conviene ofrecer</p>
          <p className="mt-1 text-sm">
            {dessert && valid.length
              ? `Solo ${withDessert} de ${valid.length} pedidos llevaron postre. Sabi ya ofrece ${dessert.name}; destácalo en tu historia de hoy.`
              : "Cuando entren pedidos, aquí verás qué sumar para subir el ticket."}
          </p>
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3 border-t pt-4">
        <p className="text-sm text-stone-600">Tu link de pedidos</p>
        <code className="truncate rounded bg-stone-100 px-2 py-1 text-xs">{link}</code>
        <button
          onClick={() => { navigator.clipboard.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
          className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-800">
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
    </div>
  );
}

type Conv = {
  id: number; status: string; customer_phone: string; customer_name: string;
  updated_at: string; messages: { id: number; direction: string; body: string; created_at: string }[];
};

export default function Registro() {
  const [today, setToday] = useState<any>(null);
  const [convs, setConvs] = useState<Conv[]>([]);
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    api("/today").then(setToday).catch(() => {});
    api("/conversations").then(setConvs).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Registro del día</h1>
      <Copiloto />
      {today && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[["Pedidos", today.orders_total], ["Aprobados", today.approved],
            ["Rechazados", today.rejected], ["Pendientes", today.pending],
            ["Convers. abiertas", today.open_conversations]].map(([label, v]) => (
            <div key={label as string} className="rounded-xl border bg-white p-3 text-center">
              <p className="text-2xl font-bold">{v as number}</p>
              <p className="text-xs text-stone-500">{label}</p>
            </div>
          ))}
        </div>
      )}
      <h2 className="mb-2 font-semibold">Conversaciones</h2>
      <div className="space-y-2">
        {convs.map((c) => (
          <div key={c.id} className="rounded-xl border bg-white">
            <button onClick={() => setOpen(open === c.id ? null : c.id)}
              className="flex w-full items-center justify-between p-3 text-left text-sm">
              <span className="font-medium">{c.customer_name || c.customer_phone}</span>
              <span className="text-stone-500">
                {c.status} · {new Date(c.updated_at).toLocaleString("es")}
              </span>
            </button>
            {open === c.id && (
              <div className="space-y-1 border-t p-3">
                {c.messages.map((m) => (
                  <p key={m.id} className={`max-w-[80%] rounded-lg p-2 text-sm ${
                    m.direction === "inbound" ? "bg-stone-100" : "ml-auto bg-emerald-100"}`}>
                    {m.body}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
