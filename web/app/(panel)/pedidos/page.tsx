"use client";
import { useEffect, useState } from "react";
import Mascot from "../../../components/Mascot";
import { api } from "../../../lib/api";
import { bs, eur, usd, type Rates } from "../../../lib/money";

type OrderItem = { id: number; name: string; quantity: number; unit_price: number; extras: string; notes: string };
type Order = {
  id: number; status: string; order_type: string; address: string; notes: string;
  total: number; source?: string; customer_phone: string; customer_name: string; created_at: string;
  payment_status: string; payment_method: string; payment_reference: string;
  items: OrderItem[];
};

export default function Pedidos() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [rate, setRate] = useState<Rates>({ usd: 0, eur: 0 });

  useEffect(() => { api("/me").then((r) => setRate({ usd: r.exchange_rate, eur: r.eur_rate })).catch(() => {}); }, []);

  async function load() {
    try {
      setOrders(await api("/orders?status=pending"));
    } catch (e) {
      setError("No autenticado. Entrá desde /login.");
    }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  async function act(id: number, action: string, body?: object) {
    await api(`/orders/${id}/${action}`, { method: "POST", body: JSON.stringify(body ?? {}) });
    setRejecting(null);
    setReason("");
    load();
  }

  const paymentLabel: Record<string, string> = {
    pago_movil: "Pago móvil", zelle: "Zelle", transferencia: "Transferencia", efectivo: "Efectivo",
  };

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Bandeja de aprobación</h1>
      {error && <p className="text-red-600">{error}</p>}
      {orders.length === 0 && !error && (
        <div className="flex flex-col items-center gap-3 py-12 text-center text-stone-500">
          <Mascot pose="idle" className="w-24" />
          <p>No hay pedidos pendientes. Sabi te avisa cuando entre uno.</p>
        </div>
      )}
      <div className="space-y-4">
        {orders.map((o) => (
          <div key={o.id} className="rounded-xl border bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-semibold">Pedido #{o.id} — {usd(o.total)}
                  <span className="ml-2 font-normal text-stone-500">{eur(o.total, rate)} · {bs(o.total, rate)}</span></p>
                <p className="text-sm text-stone-500">
                  {o.source === "tienda" ? "Tienda web · " : "WhatsApp · "}{o.customer_name || o.customer_phone} · {o.order_type}
                  {o.address ? ` · ${o.address}` : ""}
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
              <span className="rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800">
                pendiente
              </span>
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
            <div className="mt-3 flex gap-2">
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
    </div>
  );
}
