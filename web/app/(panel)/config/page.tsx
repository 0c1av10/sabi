"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Rates = { exchange_rate: number; eur_rate: number; bcv_auto?: boolean | null; rates_date?: string | null };

export default function Config() {
  const [form, setForm] = useState({ welcome_message: "", opening_hours: "", owner_phone: "", name: "", exchange_rate: "", eur_rate: "", delivery_fee: "", delivery_info: "" });
  const [auto, setAuto] = useState(true);
  const [ratesDate, setRatesDate] = useState("");
  const [saved, setSaved] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  function applyRates(r: Rates) {
    setForm((f) => ({ ...f, exchange_rate: String(r.exchange_rate), eur_rate: String(r.eur_rate) }));
    setAuto(!!r.bcv_auto);
    setRatesDate(r.rates_date || "");
  }

  useEffect(() => {
    api("/me").then((r) => {
      setForm({
        welcome_message: r.welcome_message, opening_hours: r.opening_hours,
        owner_phone: r.owner_phone, name: r.name, exchange_rate: String(r.exchange_rate), eur_rate: String(r.eur_rate),
        delivery_fee: r.delivery_fee === null || r.delivery_fee === undefined ? "" : String(r.delivery_fee),
        delivery_info: r.delivery_info || "",
      });
      applyRates(r);
    }).catch(() => {});
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const feeText = form.delivery_fee.trim().replace(",", ".");
    const fee = feeText === "" ? null : parseFloat(feeText);
    if (fee !== null && (Number.isNaN(fee) || fee < 0 || fee > 99)) {
      setError("El delivery debe ser un monto en dólares entre 0 y 99.");
      return;
    }
    const r = await api("/settings", { method: "PUT", body: JSON.stringify({
      ...form,
      delivery_fee: fee === null ? undefined : fee,
      clear_delivery_fee: fee === null,
      bcv_auto: auto,
      exchange_rate: parseFloat(form.exchange_rate.replace(",", ".")) || undefined,
      eur_rate: parseFloat(form.eur_rate.replace(",", ".")) || undefined,
    }) });
    applyRates(r);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function syncNow() {
    setSyncing(true);
    setError("");
    try {
      applyRates(await api("/settings/bcv", { method: "POST" }));
    } catch {
      setError("No se pudo consultar el BCV. Se mantienen las tasas actuales.");
    } finally {
      setSyncing(false);
    }
  }

  const field = (key: keyof typeof form, label: string, area = false, readOnly = false) => (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      {area
        ? <textarea className="w-full rounded border p-2" rows={3} value={form[key]}
            onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
        : <input className={`w-full rounded border p-2 ${readOnly ? "bg-stone-50 text-stone-500" : ""}`} value={form[key]} readOnly={readOnly}
            onChange={(e) => setForm({ ...form, [key]: e.target.value })} />}
    </label>
  );

  const fecha = ratesDate ? ratesDate.split("-").reverse().join("/") : "";

  return (
    <div className="max-w-lg">
      <h1 className="mb-4 text-xl font-semibold">Configuración</h1>
      <form onSubmit={save} className="space-y-4 rounded-xl border bg-white p-4">
        {field("name", "Nombre del restaurante")}
        {field("welcome_message", "Mensaje de bienvenida", true)}
        {field("opening_hours", "Horarios")}
        <fieldset className="space-y-3 rounded-lg border p-3">
          <legend className="px-1 text-sm font-medium">Delivery</legend>
          {field("delivery_fee", "Costo de delivery en dólares (0 = gratis, vacío = lo confirma el local)")}
          {field("delivery_info", "Zonas y condiciones (se muestran al cliente)", true)}
          <p className="text-xs text-stone-500">Se lee de tu página web al crear la tienda. Revísalo y corrígelo si hace falta.</p>
        </fieldset>
        <fieldset className="space-y-3 rounded-lg border p-3">
          <label className="flex items-center gap-2 text-sm font-medium">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
            Usar la tasa oficial del BCV (se actualiza sola)
          </label>
          {field("exchange_rate", "Tasa dólar (Bs por 1 USD)", false, auto)}
          {field("eur_rate", "Tasa euro (Bs por 1 EUR)", false, auto)}
          <div className="flex items-center justify-between text-xs text-stone-500">
            <span>{auto ? (fecha ? `Tasa BCV del ${fecha}` : "Tasa BCV") : "Tasas puestas a mano"}</span>
            {auto && (
              <button type="button" onClick={syncNow} disabled={syncing}
                className="rounded border px-3 py-1 font-medium text-stone-700 disabled:opacity-50">
                {syncing ? "Actualizando…" : "Actualizar ahora"}
              </button>
            )}
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </fieldset>
        {field("owner_phone", "WhatsApp del dueño (notificaciones de pedidos)")}
        <button className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white">
          {saved ? "Guardado ✓" : "Guardar"}
        </button>
      </form>
    </div>
  );
}
