"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Me = { slug: string; name: string; website?: string; tagline?: string; logo_url?: string; brand_color?: string; email?: string };

export default function TiendaPanel() {
  const [me, setMe] = useState<Me | null>(null);
  const [form, setForm] = useState({ website: "", tagline: "", logo_url: "", brand_color: "", email: "" });
  const [origin, setOrigin] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  function apply(r: Me) {
    setMe(r);
    setForm({ website: r.website || "", tagline: r.tagline || "", logo_url: r.logo_url || "", brand_color: r.brand_color || "", email: r.email || "" });
  }

  useEffect(() => {
    setOrigin(window.location.origin);
    api("/me").then(apply).catch(() => setMsg("No autenticado. Entra desde /login."));
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    apply(await api("/settings", { method: "PUT", body: JSON.stringify(form) }));
    setMsg("Guardado.");
  }

  async function reimport() {
    setBusy(true);
    setMsg("");
    try {
      await api("/settings", { method: "PUT", body: JSON.stringify({ website: form.website }) });
      const r = await api("/store/import", { method: "POST" });
      setMsg(r.imported ? `Listo: ${r.imported} platos leídos de ${r.website}. Revísalos en Menú.` : "Leímos la web, pero no encontramos platos con precio.");
      apply(await api("/me"));
    } catch {
      setMsg("No pudimos leer esa página web.");
    } finally {
      setBusy(false);
    }
  }

  if (!me) return <p className="text-stone-500">{msg}</p>;
  const url = `${origin}/tienda/${me.slug}`;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Tu tienda</h1>
        <p className="text-sm text-stone-500">Los pedidos de la tienda llegan a Pedidos y se confirman cuando los apruebas.</p>
      </div>

      <div className="rounded-xl border bg-white p-4 shadow-sm">
        <p className="text-sm text-stone-500">Link para compartir en Instagram, Google Maps o un QR</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <code className="flex-1 truncate rounded bg-stone-100 px-3 py-2 text-sm">{url}</code>
          <button onClick={() => { navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
            className="rounded bg-stone-200 px-3 py-2 text-sm font-medium">{copied ? "Copiado" : "Copiar"}</button>
          <a href={`/tienda/${me.slug}`} target="_blank" className="rounded bg-emerald-600 px-3 py-2 text-sm font-medium text-white">Abrir tienda</a>
        </div>
      </div>

      <div className="rounded-xl border bg-white p-4 shadow-sm">
        <p className="font-medium">Leer la carta desde tu web</p>
        <p className="text-sm text-stone-500">Sabi agrega los platos nuevos y actualiza los precios. No borra lo que ya cargaste.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input className="flex-1 rounded border p-2 text-sm" placeholder="https://turestaurante.com" value={form.website}
            onChange={(e) => setForm({ ...form, website: e.target.value })} />
          <button onClick={reimport} disabled={busy || !form.website} className="rounded bg-emerald-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
            {busy ? "Leyendo…" : "Leer mi web"}
          </button>
        </div>
      </div>

      <form onSubmit={save} className="space-y-3 rounded-xl border bg-white p-4 shadow-sm">
        <p className="font-medium">Cómo se ve</p>
        <label className="block text-sm">Frase corta
          <input className="mt-1 w-full rounded border p-2" value={form.tagline} onChange={(e) => setForm({ ...form, tagline: e.target.value })} />
        </label>
        <label className="block text-sm">Logo (URL de la imagen)
          <div className="mt-1 flex items-center gap-2">
            {form.logo_url && <img src={form.logo_url} alt="" className="h-10 w-10 rounded border object-contain p-0.5" />}
            <input className="flex-1 rounded border p-2" value={form.logo_url} onChange={(e) => setForm({ ...form, logo_url: e.target.value })} />
          </div>
        </label>
        <label className="block text-sm">Color de la marca
          <div className="mt-1 flex items-center gap-2">
            <input type="color" className="h-10 w-14 rounded border" value={form.brand_color || "#25D366"} onChange={(e) => setForm({ ...form, brand_color: e.target.value })} />
            <span className="font-mono text-stone-500">{form.brand_color || "#25D366"}</span>
          </div>
        </label>
        <label className="block text-sm">Correo del local
          <input type="email" className="mt-1 w-full rounded border p-2" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </label>
        <button className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white">Guardar</button>
      </form>
      {msg && <p className="text-sm text-stone-600">{msg}</p>}
    </div>
  );
}
