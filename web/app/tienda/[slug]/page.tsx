"use client";
import { useEffect, useMemo, useState } from "react";
import Mascot from "../../../components/Mascot";
import { ink } from "../../../lib/brand";
import { bs, eur, usd, type Rates } from "../../../lib/money";

type Item = { id: number; name: string; price: number; category: string; description: string; image_url: string };
type Store = {
  name: string; slug: string; tagline: string; logo_url: string; brand_color: string;
  opening_hours: string; whatsapp: string; rates: Rates; menu: Item[];
  delivery_fee: number | null; delivery_info: string;
};

const input = "w-full rounded-xl border border-stone-200 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-stone-400";

export default function Tienda({ params }: { params: { slug: string } }) {
  const [store, setStore] = useState<Store | null>(null);
  const [missing, setMissing] = useState(false);
  const [cart, setCart] = useState<Record<number, number>>({});
  const [open, setOpen] = useState(false);
  const [checkout, setCheckout] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", order_type: "delivery", address: "", notes: "", payment_method: "pago_movil", payment_reference: "" });
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<number | null>(null);

  useEffect(() => {
    fetch(`/api/store/${params.slug}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((s: Store) => { setStore(s); document.title = `${s.name} · Pide en línea`; })
      .catch(() => setMissing(true));
  }, [params.slug]);

  const groups = useMemo(() => {
    const g: [string, Item[]][] = [];
    store?.menu.forEach((i) => {
      const last = g.find(([c]) => c === i.category);
      last ? last[1].push(i) : g.push([i.category, [i]]);
    });
    return g;
  }, [store]);

  if (missing) return <p className="p-10 text-center text-stone-500">No encontramos esta tienda.</p>;
  if (!store) return <div className="min-h-screen bg-stone-50" />;

  const brand = store.brand_color;
  const onBrand = ink(brand);
  const R = store.rates;
  const lines = store.menu.filter((i) => cart[i.id]).map((i) => ({ ...i, qty: cart[i.id] }));
  const count = lines.reduce((s, l) => s + l.qty, 0);
  const subtotal = lines.reduce((s, l) => s + l.qty * l.price, 0);
  const isDelivery = form.order_type === "delivery";
  const fee = isDelivery ? (store.delivery_fee ?? 0) : 0;
  const total = subtotal + fee;
  const add = (id: number, d: number) =>
    setCart((c) => { const n = { ...c, [id]: Math.max(0, (c[id] || 0) + d) }; if (!n[id]) delete n[id]; return n; });

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);
    setError("");
    const res = await fetch(`/api/store/${store!.slug}/orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form, items: lines.map((l) => ({ menu_item_id: l.id, quantity: l.qty })) }),
    });
    setSending(false);
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      return setError(typeof d.detail === "string" ? d.detail : "Revisa tu nombre y tu WhatsApp.");
    }
    setDone((await res.json()).order_id);
    setCart({});
  }

  const wa = store.whatsapp
    ? `https://wa.me/${store.whatsapp}?text=${encodeURIComponent(`Hola, quiero pedir en ${store.name}. [sabi:${store.slug}]`)}`
    : "";

  const cartPanel = (
    <div className="flex h-full flex-col">
      {done ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
          <Mascot className="w-24" />
          <p className="text-lg font-semibold">Tu pedido #{done} llegó a {store.name}</p>
          <p className="text-sm text-stone-500">Lo están revisando. Te confirmamos por WhatsApp apenas lo aprueben.</p>
          <button onClick={() => { setDone(null); setCheckout(false); setOpen(false); }} className="mt-2 text-sm font-medium underline">Seguir viendo la carta</button>
        </div>
      ) : !lines.length ? (
        <p className="p-6 text-sm text-stone-500">Tu pedido está vacío. Toca un plato para agregarlo.</p>
      ) : (
        <>
          <ul className="divide-y divide-stone-100 px-5">
            {lines.map((l) => (
              <li key={l.id} className="flex items-center gap-3 py-3 text-sm">
                <div className="flex items-center rounded-full border border-stone-200">
                  <button aria-label="Quitar uno" onClick={() => add(l.id, -1)} className="px-2.5 py-1">−</button>
                  <span className="w-5 text-center tabular-nums">{l.qty}</span>
                  <button aria-label="Agregar uno" onClick={() => add(l.id, 1)} className="px-2.5 py-1">+</button>
                </div>
                <span className="flex-1">{l.name}</span>
                <span className="tabular-nums">{usd(l.qty * l.price)}</span>
              </li>
            ))}
          </ul>
          {checkout && (
            <form id="checkout" onSubmit={send} className="space-y-2.5 border-t border-stone-100 px-5 py-4">
              <input required minLength={2} className={input} placeholder="Tu nombre" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input required minLength={7} type="tel" className={input} placeholder="Tu WhatsApp" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              <div className="grid grid-cols-2 gap-2 text-sm">
                {(["delivery", "retiro"] as const).map((t) => (
                  <button type="button" key={t} onClick={() => setForm({ ...form, order_type: t })}
                    className="rounded-xl border px-3 py-2 font-medium transition"
                    style={form.order_type === t ? { background: brand, color: onBrand, borderColor: brand } : { borderColor: "#e7e5e4" }}>
                    {t === "delivery" ? "Delivery" : "Paso a buscarlo"}
                  </button>
                ))}
              </div>
              {form.order_type === "delivery" && (
                <input required className={input} placeholder="Dirección de entrega" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
              )}
              <input className={input} placeholder="Notas (opcional)" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              <select className={input} value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
                <option value="pago_movil">Pago móvil</option>
                <option value="zelle">Zelle</option>
                <option value="transferencia">Transferencia</option>
                <option value="efectivo">Efectivo al retirar</option>
              </select>
              <input className={input} placeholder="Referencia o comprobante (opcional)" value={form.payment_reference} onChange={(e) => setForm({ ...form, payment_reference: e.target.value })} />
              {error && <p className="text-sm text-red-600">{error}</p>}
            </form>
          )}
          <div className="border-t border-stone-100 p-5">
            {isDelivery && checkout && (
              <div className="mb-3 space-y-1 text-sm text-stone-500">
                <div className="flex justify-between tabular-nums"><span>Pedido</span><span>{usd(subtotal)}</span></div>
                <div className="flex justify-between tabular-nums">
                  <span>Delivery</span>
                  <span>{store.delivery_fee === null ? "Lo confirma el local" : store.delivery_fee === 0 ? "Gratis" : usd(store.delivery_fee)}</span>
                </div>
                {store.delivery_info && <p className="whitespace-pre-line text-xs text-stone-400">{store.delivery_info}</p>}
              </div>
            )}
            <div className="flex items-baseline justify-between">
              <span className="text-sm text-stone-500">Total</span>
              <span className="text-xl font-semibold tabular-nums">{usd(total)}</span>
            </div>
            <p className="text-right text-xs text-stone-400 tabular-nums">{eur(total, R)} · {bs(total, R)}</p>
            {checkout ? (
              <button form="checkout" disabled={sending} className="mt-4 w-full rounded-full py-3 font-semibold transition active:scale-[0.98] disabled:opacity-60" style={{ background: brand, color: onBrand }}>
                {sending ? "Enviando…" : "Enviar pedido"}
              </button>
            ) : (
              <button onClick={() => setCheckout(true)} className="mt-4 w-full rounded-full py-3 font-semibold transition active:scale-[0.98]" style={{ background: brand, color: onBrand }}>
                Continuar
              </button>
            )}
            <p className="mt-2 text-center text-xs text-stone-400">El local verifica el pago y confirma tu pedido por WhatsApp.</p>
          </div>
        </>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <header style={{ background: brand, color: onBrand }}>
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 py-8 md:py-12">
          {store.logo_url && (
            <img src={store.logo_url} alt={`Logo de ${store.name}`} className="h-14 w-14 rounded-2xl bg-white object-contain p-1.5 md:h-16 md:w-16" />
          )}
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight md:text-4xl">{store.name}</h1>
            {store.tagline && <p className="mt-1 max-w-2xl text-sm opacity-75 md:text-base">{store.tagline}</p>}
            <p className="mt-2 text-xs opacity-60">{store.opening_hours}{wa && <> · <a href={wa} className="underline">Escríbenos por WhatsApp</a></>}</p>
          </div>
        </div>
      </header>

      <nav className="sticky top-0 z-10 border-b border-stone-200 bg-stone-50/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl gap-5 overflow-x-auto px-5 py-3 text-sm [scrollbar-width:none]">
          {groups.map(([c], i) => (
            <a key={c} href={`#cat-${i}`} className="shrink-0 text-stone-600 transition hover:text-stone-900">{c}</a>
          ))}
        </div>
      </nav>

      <div className="mx-auto grid max-w-6xl gap-10 px-5 pb-32 pt-6 lg:grid-cols-[1fr_22rem]">
        <main>
          {groups.map(([c, items], gi) => (
            <section key={c} id={`cat-${gi}`} className="scroll-mt-16 pt-6">
              <h2 className="mb-2 text-lg font-semibold">{c}</h2>
              <ul className="divide-y divide-stone-200/70">
                {items.map((i) => (
                  <li key={i.id}>
                    <button onClick={() => add(i.id, 1)} className="group flex w-full items-center gap-4 py-4 text-left">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{i.name}</p>
                        {i.description && <p className="mt-0.5 line-clamp-2 text-sm text-stone-500">{i.description}</p>}
                        <p className="mt-1.5 text-sm tabular-nums">
                          <span className="font-semibold">{usd(i.price)}</span>
                          <span className="text-stone-400"> · {eur(i.price, R)} · {bs(i.price, R)}</span>
                        </p>
                      </div>
                      {i.image_url && <img src={i.image_url} alt="" loading="lazy" className="h-20 w-20 shrink-0 rounded-xl object-cover md:h-24 md:w-24" />}
                      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-lg transition group-hover:scale-110 group-active:scale-95"
                        style={cart[i.id] ? { background: brand, color: onBrand } : { border: "1px solid #d6d3d1" }}>
                        {cart[i.id] || "+"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          <p className="mt-16 text-center text-xs text-stone-400">
            Tienda creada con <a href="/" className="font-medium text-stone-500 underline">Sabi</a>
          </p>
        </main>

        <aside className="hidden lg:block">
          <div className="sticky top-16 mt-6 max-h-[calc(100vh-5rem)] overflow-hidden rounded-3xl border border-stone-200 bg-white shadow-sm">
            <p className="border-b border-stone-100 px-5 py-4 font-semibold">Tu pedido</p>
            {cartPanel}
          </div>
        </aside>
      </div>

      {(count > 0 || done) && !open && (
        <button onClick={() => setOpen(true)} className="fixed inset-x-4 bottom-4 z-20 flex items-center justify-between rounded-full px-6 py-4 font-semibold shadow-xl lg:hidden"
          style={{ background: brand, color: onBrand }}>
          <span>{done ? "Pedido enviado" : `Ver pedido · ${count}`}</span>
          {!done && <span className="tabular-nums">{usd(total)}</span>}
        </button>
      )}
      {open && (
        <div className="fixed inset-0 z-30 flex flex-col justify-end bg-black/40 lg:hidden" onClick={() => setOpen(false)}>
          <div className="max-h-[88vh] overflow-y-auto rounded-t-3xl bg-white" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-stone-100 px-5 py-4">
              <p className="font-semibold">Tu pedido</p>
              <button onClick={() => setOpen(false)} className="text-sm text-stone-500">Cerrar</button>
            </div>
            {cartPanel}
          </div>
        </div>
      )}
    </div>
  );
}
