"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

export default function Config() {
  const [form, setForm] = useState({ welcome_message: "", opening_hours: "", owner_phone: "", name: "" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api("/me").then((r) => setForm({
      welcome_message: r.welcome_message, opening_hours: r.opening_hours,
      owner_phone: r.owner_phone, name: r.name,
    })).catch(() => {});
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    await api("/settings", { method: "PUT", body: JSON.stringify(form) });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const field = (key: keyof typeof form, label: string, area = false) => (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      {area
        ? <textarea className="w-full rounded border p-2" rows={3} value={form[key]}
            onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
        : <input className="w-full rounded border p-2" value={form[key]}
            onChange={(e) => setForm({ ...form, [key]: e.target.value })} />}
    </label>
  );

  return (
    <div className="max-w-lg">
      <h1 className="mb-4 text-xl font-semibold">Configuración</h1>
      <form onSubmit={save} className="space-y-4 rounded-xl border bg-white p-4">
        {field("name", "Nombre del restaurante")}
        {field("welcome_message", "Mensaje de bienvenida", true)}
        {field("opening_hours", "Horarios")}
        {field("owner_phone", "WhatsApp del dueño (notificaciones de pedidos)")}
        <button className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
          {saved ? "Guardado ✓" : "Guardar"}
        </button>
      </form>
    </div>
  );
}
