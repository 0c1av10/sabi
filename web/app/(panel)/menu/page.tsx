"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Item = { id: number; name: string; price: number; category: string; available: boolean; description: string };
const empty = { name: "", price: 0, category: "General", description: "" };

export default function Menu() {
  const [items, setItems] = useState<Item[]>([]);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState<number | null>(null);

  async function load() { setItems(await api("/menu")); }
  useEffect(() => { load().catch(() => {}); }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (editing) await api(`/menu/${editing}`, { method: "PUT", body: JSON.stringify(form) });
    else await api("/menu", { method: "POST", body: JSON.stringify(form) });
    setForm(empty); setEditing(null); load();
  }

  async function toggle(it: Item) {
    await api(`/menu/${it.id}`, { method: "PUT", body: JSON.stringify({ ...it, available: !it.available }) });
    load();
  }

  async function remove(id: number) {
    await api(`/menu/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Menú</h1>
      <form onSubmit={save} className="mb-6 flex flex-wrap gap-2 rounded-xl border bg-white p-4">
        <input required className="rounded border p-2" placeholder="Nombre" value={form.name}
               onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input required type="number" step="0.01" className="w-28 rounded border p-2" placeholder="Precio"
               value={form.price || ""} onChange={(e) => setForm({ ...form, price: +e.target.value })} />
        <input className="rounded border p-2" placeholder="Categoría" value={form.category}
               onChange={(e) => setForm({ ...form, category: e.target.value })} />
        <input className="flex-1 rounded border p-2" placeholder="Descripción" value={form.description}
               onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <button className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
          {editing ? "Guardar" : "Agregar"}
        </button>
      </form>
      <table className="w-full overflow-hidden rounded-xl border bg-white text-sm">
        <thead className="bg-stone-100 text-left">
          <tr><th className="p-3">Nombre</th><th>Precio</th><th>Categoría</th><th>Disponible</th><th /></tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.id} className="border-t">
              <td className="p-3">{it.name}</td>
              <td>${it.price}</td>
              <td>{it.category}</td>
              <td>
                <button onClick={() => toggle(it)}
                  className={`rounded px-2 py-1 text-xs font-medium ${it.available ? "bg-emerald-100 text-emerald-800" : "bg-stone-200 text-stone-500"}`}>
                  {it.available ? "Sí" : "No"}
                </button>
              </td>
              <td className="space-x-2 pr-3 text-right">
                <button onClick={() => { setEditing(it.id); setForm({ name: it.name, price: it.price, category: it.category, description: it.description }); }}
                  className="text-emerald-700">Editar</button>
                <button onClick={() => remove(it.id)} className="text-red-600">Borrar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
