"use client";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

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
