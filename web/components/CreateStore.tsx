"use client";
import Link from "next/link";
import { useState } from "react";

type Result = { slug: string; pin: string; name: string; imported: number; site_read: boolean; store_path: string };

const field = "w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-white placeholder:text-emerald-50/40 outline-none transition focus:border-[#25D366]/60 focus:bg-white/[0.07]";

export default function CreateStore() {
  const [form, setForm] = useState({ name: "", email: "", phone: "", website: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/onboarding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error();
      setResult(await res.json());
    } catch {
      setError("Revisa el correo y el WhatsApp e inténtalo de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-2">
        <div className="rounded-[calc(2rem-0.5rem)] bg-[#06281e] p-8">
          <p className="text-2xl font-semibold tracking-tight">La tienda de {result.name} está lista</p>
          <p className="mt-2 text-emerald-50/70">
            {result.imported
              ? `Sabi leyó tu web y cargó ${result.imported} platos con sus precios. Revísalos en el panel.`
              : result.site_read
                ? "Leímos tu web, pero no encontramos la carta. Arrancas con un menú base que editas en el panel."
                : "Arrancas con un menú base que editas en el panel."}
          </p>
          <div className="mt-6 grid gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-xl bg-white/[0.05] px-4 py-3">Usuario <span className="ml-2 font-mono text-base text-white">{result.slug}</span></div>
            <div className="rounded-xl bg-white/[0.05] px-4 py-3">PIN <span className="ml-2 font-mono text-base text-white">{result.pin}</span></div>
          </div>
          <p className="mt-3 text-xs text-emerald-50/50">Tu interfaz, menú, marca y agente quedan personalizados para este negocio. Guarda tu PIN: por ahora no lo enviamos por correo.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href={result.store_path} target="_blank" className="rounded-full bg-[#25D366] px-6 py-3 font-semibold text-[#04140f] transition hover:scale-[1.03] active:scale-[0.98]">
              Ver mi tienda
            </a>
            <Link href={`/login?slug=${result.slug}`} className="rounded-full border border-white/15 px-6 py-3 font-medium text-white transition hover:bg-white/10">
              Entrar a mi panel
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-2">
      <div className="grid gap-3 rounded-[calc(2rem-0.5rem)] bg-[#06281e] p-6 sm:grid-cols-2 sm:p-8">
        <input required minLength={2} className={field} placeholder="Nombre del local" value={form.name} onChange={set("name")} />
        <input required type="email" className={field} placeholder="Correo" value={form.email} onChange={set("email")} />
        <input required minLength={7} type="tel" className={field} placeholder="WhatsApp del local" value={form.phone} onChange={set("phone")} />
        <input className={field} placeholder="Página web (opcional)" value={form.website} onChange={set("website")} />
        {error && <p className="text-sm text-red-300 sm:col-span-2">{error}</p>}
        <button disabled={busy} className="mt-2 rounded-full bg-[#25D366] px-6 py-3.5 font-semibold text-[#04140f] shadow-lg shadow-[#25D366]/25 transition hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 sm:col-span-2">
          {busy ? "Sabi está leyendo tu web…" : "Crear mi tienda"}
        </button>
      </div>
    </form>
  );
}
