import Link from "next/link";

const chat = [
  { who: "c", text: "Hola! Quiero pedir 2 milanesas napolitanas y una gaseosa", time: "21:03" },
  { who: "s", text: "Anoté: 2 x Milanesa napolitana, 1 x Gaseosa 1.5L. ¿Delivery o retiro?", time: "21:03" },
  { who: "c", text: "Delivery, Av. Italia 1234", time: "21:04" },
  { who: "s", text: "Tu pedido: 2 milanesas + 1 gaseosa. Total: $10,20 · €9,40 · Bs 372,30. ¿Está correcto?", time: "21:04" },
  { who: "c", text: "Sí", time: "21:05" },
];

const features = [
  {
    title: "Atiende y toma pedidos 24/7",
    desc: "Responde menú, precios y horarios al instante. Conversa hasta completar el pedido: ítems, cantidades, extras, delivery o retiro, dirección y total en dólares, euros y bolívares.",
  },
  {
    title: "Vos aprobás cada pedido",
    desc: "Nada se confirma solo. Cada pedido llega a tu bandeja con el resumen completo y lo aprobás, editás o rechazás con un toque. Recién ahí el cliente recibe la confirmación.",
  },
  {
    title: "Dólares, euros y bolívares",
    desc: "Cargás el menú en dólares y las tasas del día. Sabi le da a cada cliente el precio en las tres monedas, sin cuentas a mano ni tasas viejas.",
  },
  {
    title: "Todo queda registrado",
    desc: "Cada conversación y pedido guardado. Vista del día con aprobados, rechazados y consultas sin cerrar. Sin audios que no se escucharon ni notas a mano.",
  },
];

export default function Landing() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="border-b">
        <div className="mx-auto grid max-w-6xl gap-12 px-6 py-20 md:grid-cols-2 md:items-center">
          <div>
            <h1 className="text-4xl font-bold leading-tight tracking-tight md:text-5xl">
              El vendedor de WhatsApp que nunca pierde un pedido
            </h1>
            <p className="mt-5 text-lg text-stone-600">
              Sabi atiende a tus clientes las 24 horas, toma el pedido completo y
              te lo manda para que lo apruebes. Vos decidís — la IA nunca confirma sola.
            </p>
            <div className="mt-8 flex gap-3">
              <Link href="/login" className="rounded-lg bg-emerald-700 px-6 py-3 font-medium text-white hover:bg-emerald-800">
                Probar el panel
              </Link>
              <a href="#como-funciona" className="rounded-lg border px-6 py-3 font-medium text-stone-700 hover:bg-stone-50">
                Cómo funciona
              </a>
            </div>
          </div>

          {/* WhatsApp mock */}
          <div className="rounded-3xl border bg-[#ece5dd] p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2 border-b border-stone-300/60 pb-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-700 text-sm font-bold text-white">S</div>
              <div>
                <p className="text-sm font-semibold">La Esquina · Sabi</p>
                <p className="text-xs text-emerald-700">en línea</p>
              </div>
            </div>
            <div className="space-y-2">
              {chat.map((m, i) => (
                <div key={i} className={`max-w-[85%] rounded-lg px-3 py-2 text-sm shadow-sm ${
                  m.who === "c" ? "ml-auto bg-[#dcf8c6]" : "bg-white"}`}>
                  <p>{m.text}</p>
                  <p className="mt-0.5 text-right text-[10px] text-stone-400">{m.time}</p>
                </div>
              ))}
              <div className="ml-auto w-fit rounded-lg border border-emerald-600 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
                Pedido enviado al dueño · pendiente de aprobación
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Metrics strip */}
      <section className="border-b bg-emerald-900 text-white">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-6 py-10 text-center md:grid-cols-3">
          {[["24 h", "Atención todos los días"],
            ["100%", "Pedidos que pasan por tu aprobación"],
            ["0", "Pedidos confirmados sin tu ok"]].map(([n, l]) => (
            <div key={l}>
              <p className="text-3xl font-bold">{n}</p>
              <p className="mt-1 text-sm text-emerald-200">{l}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-3xl font-bold tracking-tight">Todo lo que necesitás para vender por WhatsApp</h2>
        <p className="mt-3 max-w-2xl text-stone-600">
          Un sistema completo: el agente conversa, estructura el pedido y vos tenés la última palabra.
        </p>
        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {features.map((f) => (
            <div key={f.title} className="rounded-2xl border p-6">
              <h3 className="text-lg font-semibold">{f.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-600">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="como-funciona" className="border-t bg-stone-50">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="text-3xl font-bold tracking-tight">Así funciona</h2>
          <div className="mt-10 grid gap-8 md:grid-cols-3">
            {[
              ["El cliente pide", "Escribe por WhatsApp como siempre. Sabi le muestra el menú, responde precios y horarios, y arma el pedido con ítems, cantidades y dirección."],
              ["Vos aprobás", "El pedido llega a tu bandeja con el resumen completo. Lo aprobás, lo editás o lo rechazás con motivo — desde el celular o la compu."],
              ["El cliente recibe", "Recién cuando aprobás, el cliente recibe la confirmación por WhatsApp. Todo queda guardado en el registro del día."],
            ].map(([t, d]) => (
              <div key={t}>
                <h3 className="text-lg font-semibold text-emerald-800">{t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-stone-600">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t">
        <div className="mx-auto max-w-6xl px-6 py-20 text-center">
          <h2 className="text-3xl font-bold tracking-tight">Dejá que la IA tome los pedidos — sin soltar el control</h2>
          <p className="mx-auto mt-4 max-w-xl text-stone-600">
            Piloto para 1 a 3 restaurantes. Menú cargado, número de WhatsApp y listo.
          </p>
          <Link href="/login" className="mt-8 inline-block rounded-lg bg-emerald-700 px-8 py-3 font-medium text-white hover:bg-emerald-800">
            Entrar al panel
          </Link>
        </div>
      </section>
    </div>
  );
}
